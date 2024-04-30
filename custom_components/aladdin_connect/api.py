"""API setup for Aladdin Connect."""

import asyncio
import base64
import hmac
import json
from collections.abc import Callable

from cachetools import TTLCache
from pubsub import pub
from pubsub.core import Listener

from .const import DOOR_LINK_STATUS, DOOR_STATUS, MODEL_MAP, DoorCommand, DoorStatus
from .model import DoorDevice


class AladdinConnect:
    """Aladdin Connect client class."""

    API_HOST = 'api.smartgarage.systems'
    AUTH_CLIENT_ID = '27iic8c3bvslqngl3hso83t74b'
    AUTH_CLIENT_SECRET = '7bokto0ep96055k42fnrmuth84k7jdcjablestb7j53o8lp63v5'
    AUTH_HOST = 'cognito-idp.us-east-2.amazonaws.com'
    DOOR_STATUS_LOCK = asyncio.Lock()
    DOOR_STATUS_POLL_INTERVAL_MS_DEFAULT = 15000
    DOOR_STATUS_POLL_INTERVAL_MS_MAX = 60000
    DOOR_STATUS_POLL_INTERVAL_MS_MIN = 5000
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_DEFAULT = 15
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_MAX = 60
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_MIN = 5
    PUB_SUB_DOOR_STATUS_TOPIC = 'door'

    def __init__(self, logger, session, config):
        """Set up base information."""
        self.log = logger
        self._config = config
        self._cache = TTLCache(maxsize=1024, ttl=self._door_status_stationary_cache_ttl())
        self._doors: list[DoorDevice] = []
        self._session = session
        self._subscribers_count = {}

    async def get_access_token(self, encoding='utf-8'):
        """Log in to AladdinConnect service and get access token."""
        digest = hmac.new(
            self.AUTH_CLIENT_SECRET.encode(encoding),
            (self._config['username'] + self.AUTH_CLIENT_ID).encode(encoding),
            'sha256'
        ).digest()
        secret_hash = base64.b64encode(digest).decode()
        async with self._session.post(
            f'https://{self.AUTH_HOST}',
            json={
                'ClientId': self.AUTH_CLIENT_ID,
                'AuthFlow': 'USER_PASSWORD_AUTH',
                'AuthParameters': {
                    'USERNAME': self._config['username'],
                    'PASSWORD': self._config['password'],
                    'SECRET_HASH': secret_hash,
                },
            },
            headers={'Content-Type': 'application/x-amz-json-1.1', 'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'}) as response:
                response.raise_for_status()
                data = await response.json(content_type='application/x-amz-json-1.1')
                return data['AuthenticationResult']['AccessToken']

    async def get_doors(self, serial: str = None):
        """Retrieve all door statuses, refreshing from the service if needed."""
        cache_key = self._door_status_cache_key(serial)

        if cache_key in self._cache:
            return self._cache[cache_key]

        return await self._cache_all_doors(serial)

    async def open_door(self, door: DoorDevice):
        """Command to open the door."""
        return await self._set_door_status(door, DoorStatus.OPEN)

    async def close_door(self, door: DoorDevice):
        """Command to close the door."""
        return await self._set_door_status(door, DoorStatus.CLOSED)

    async def subscribe(self, door: DoorDevice, func: Callable) -> Listener:
        """Subscribe to status updates for a specific door."""
        topic_name = self._door_status_topic(door)
        is_first_subscription = self._get_subscriber_count(topic_name) == 0
        listener = self._subscribe_to_topic(lambda data: func(data), topic_name)
        self.log.debug(f'[API] Status subscription added for door {door.name} [listener={listener}]')

        if is_first_subscription:
            async def poll():
                if self._get_subscriber_count(topic_name) == 0:
                    self.log.debug(f'[API] No door status subscriptions for [{topic_name}]; skipping poll')
                    return

                self.log.debug(f'[API] Polling [{topic_name}] for status updates')
                try:
                    doors = await self.get_doors()
                    for door in doors:
                        self.log.debug(f'[API] Emitting message for {door.name} [{topic_name}]')
                        pub.sendMessage(self._door_status_topic(door), data=door)
                except Exception:
                    # log exception and trap, don't interrupt publish
                    pass

                # Schedule next poll operation
                asyncio.get_running_loop().call_later(
                    self._poll_interval_ms() / 1000,
                    lambda: asyncio.create_task(poll())
                    )

            # immediately start polling
            await asyncio.create_task(poll())

        return listener

    def unsubscribe(self, listener: Listener, door: DoorDevice) -> None:
        """Unsubscribe from door status updates."""
        topic = self._door_status_topic(door)
        self._unsubscribe_from_topic(listener, topic)
        self.log.debug(f'[API] Status subscription removed for {door.name} [listener={listener}]')

    def _get_subscriber_count(self, topic_name:str) -> int:
        """Get subscriber count for a given topic."""
        return self._subscribers_count.get(topic_name, 0)

    def _subscribe_to_topic(self, func: Callable, topic_name: str) -> Listener:
        """Wrap PyPubSub calls to subscribe() to track subscriber count."""
        if topic_name not in self._subscribers_count:
            self._subscribers_count[topic_name] = 0
        self._subscribers_count[topic_name] += 1
        return pub.subscribe(lambda data: func(data), topic_name)

    def _unsubscribe_from_topic(self, listener: Listener, topic_name: str):
        """Wrap PyPubSub calls to unsubscribe() to track subscriber count."""
        if topic_name in self._subscribers_count:
            self._subscribers_count[topic_name] -= 1
        if self._subscribers_count[topic_name] == 0:
            del self._subscribers_count[topic_name]
        pub.unsubscribe(listener, topic_name)

    async def _cache_all_doors(self, serial: str = None) -> list[DoorDevice]:
        """Call out to AladdinConnect service to retrieve all device and door info."""

        cache_key = self._door_status_cache_key(serial)

        if cache_key in self._cache:
            doors_data = self._cache[cache_key]
            return doors_data

        headers = {
            'Authorization': f'Bearer {await self.get_access_token()}'
        }
        async with self.DOOR_STATUS_LOCK, self._session.get(f'https://{self.API_HOST}/devices', headers=headers) as response:
                if response.status != 200:
                    error_message = await response.text()
                    self.log.error(f'[API] An error occurred getting devices from account; {error_message}')
                    response.raise_for_status()

                data = json.loads(json.dumps(await response.json()))
                self.log.debug(f'[API] Configuration response: {data}')

                doors: list[DoorDevice] = []

                for device in data["devices"]:
                    self.log.debug(f'[API] Found device: {device}')
                    for door in device["doors"]:
                        self.log.debug(f'[API] Found door: {door}')

                        if serial is not None and device["serial_number"] != serial:
                            continue

                        door_data = DoorDevice(
                            battery_level=door.get('battery_level', 0),
                            ble_strength=device.get('ble_strength', 0),
                            device_id=device.get("id"),
                            fault=bool(door.get('fault')),
                            has_battery_level=(door.get('battery_level', 0) > 0),
                            has_ble_strength=(door.get('ble_strength', 0) > 0),
                            id=door['id'],
                            index=door['door_index'],
                            link_status=DOOR_LINK_STATUS[door.get("link_status", 0)],
                            manufacturer=device.get('vendor', 'UNKNOWN'),
                            model=MODEL_MAP.get(device.get('model', 'UKNOWN'), 'UNKNOWN'),
                            name=door.get('name', 'Garage Door'),
                            ownership=device['ownership'],
                            rssi=device.get("rssi", 0),
                            serial_number=device['serial_number'],
                            software_version=device.get('software_version', 'UNKNOWN'),
                            ssid=device.get('ssid', 'UNKNOWN'),
                            status=DOOR_STATUS[door.get('status', 0)],
                        )
                        self._cache[door_data.serial_number] = door_data
                        doors.append(door_data)
                self._doors = doors
                self._cache['all_doors'] = doors
                return doors

    async def _set_door_status(self, door: DoorDevice, desired_status: DoorStatus) -> None:
        """Send a command to the service to set a door's status."""
        async with self.DOOR_STATUS_LOCK:
            command = DoorCommand.OPEN if desired_status == DoorStatus.OPEN else DoorCommand.CLOSE
            headers = {'Authorization': f'Bearer {await self.get_access_token()}'}
            self.log.debug(f'[API] Requesting [{command}] on {door.name}')
            try:
                async with self._session.post(
                    f'https://{self.API_HOST}/command/devices/{door.device_id}/doors/{door.index}',
                    json={'command': command},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_message = await response.text()
                        self.log.error(f'[API] An error occurred sending command {command} to door {door.name}; {error_message}')
                        response.raise_for_status()

                    data = await response.json()
                    self.log.debug(f'[API] Genie {command} response: {data}')

            except Exception as error:
                self.log.error(f'[API] An error occurred sending command {command} to door {door.name}; {error}')
                return False

            await self._invalidate_door_cache(door)
            door.status = desired_status
            pub.sendMessage(self._door_status_topic(door), data=door)
            return True

    async def _invalidate_door_cache(self, door: DoorDevice) -> None:
        """Invalidate the cache for a specific door."""

        cache_key = self._door_status_cache_key(door)
        if cache_key in self._cache:
            del self._cache[cache_key]
            self.log.debug(f'[API] Cache invalidated for {cache_key}')
        else:
            self.log.debug(f'[API] No cache entry found for {cache_key} to invalidate')

    def _door_status_stationary_cache_ttl(self):
        """Compute TTL for stationary door status, with bounds checking."""
        return max(
            self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_MIN,
            min(
                self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_MAX,
                self._config.get('doorStatusStationaryCacheTtl', self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_DEFAULT)
            )
        )

    def _poll_interval_ms(self):
        """Compute the polling interval in milliseconds, with bounds checking."""
        return max(
            self.DOOR_STATUS_POLL_INTERVAL_MS_MIN,
            min(
                self.DOOR_STATUS_POLL_INTERVAL_MS_MAX,
                self._config.get('doorStatusPollInterval', self.DOOR_STATUS_POLL_INTERVAL_MS_DEFAULT)
            )
        )

    @staticmethod
    def _door_status_cache_key(door: DoorDevice) -> str:
        """Construct a unique cache key string based on door information."""
        return door.serial_number

    @staticmethod
    def _door_status_cache_key(serial: str = None) -> str:
        """Construct a unique cache key based on serial number."""
        return 'all_doors' if serial is None else serial

    @staticmethod
    def _door_status_topic(door: DoorDevice) -> str:
        """Construct a unique pub/sub topic string based on door information."""
        return f'{AladdinConnect.PUB_SUB_DOOR_STATUS_TOPIC}.{door.device_id}.{door.index}'
