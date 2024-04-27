"""API setup for Aladdin Connect."""

import asyncio
import base64
import hmac
import json
from collections.abc import Callable
from functools import partial

import aiohttp
from cachetools import TTLCache, cachedmethod
from cachetools.keys import hashkey
from pubsub import pub
from pubsub.core import Listener

from .const import DOOR_LINK_STATUS, DOOR_STATUS, MODEL_MAP, DoorCommand, DoorStatus
from .model import DoorDevice


class AladdinConnect:
    """Aladdin Connect client class, managing garage door devices."""

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
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_DEFAULT = 5
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MAX = 30
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MIN = 1
    PUB_SUB_DOOR_STATUS_TOPIC = 'door'

    def __init__(self, logger, config):
        """Initialize the client with logging and configuration."""
        self._cache = TTLCache(maxsize=1024, ttl=self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_DEFAULT)
        self._config = config
        self._doors = []
        self._session = None  # Will be initialized in an async context
        self._subscribers_count = {}
        self.log = logger

    async def init_session(self):
        """Initialize the HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close_session(self):
        """Close the HTTP session."""
        if self._session:
            await self._session.close()

    async def get_access_token(self):
        """Authenticate and retrieve access token from AladdinConnect service."""
        digest = hmac.new(
            self.AUTH_CLIENT_SECRET.encode(),
            (self._config['username'] + self.AUTH_CLIENT_ID).encode(),
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
            headers={'Content-Type': 'application/x-amz-json-1.1', 'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'}
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type='application/x-amz-json-1.1')
            return data['AuthenticationResult']['AccessToken']

    async def get_doors(self, serial=None):
        """Retrieve all door statuses, refreshing from the service if needed."""
        if not self._doors:
            await self.cache_all_doors(serial)
        return self._doors

    async def fetch_door_data(self, headers):
        """Fetch the door data from API."""
        url = f'https://{self.API_HOST}/devices'
        async with self._session.get(url, headers=headers) as response:
            if response.status != 200:
                error_message = await response.text()
                self.log.error(f'[API] An error occurred getting devices from account; {error_message}')
                response.raise_for_status()
            return await response.json()

    async def process_door_data(self, data, serial):
        """Process the JSON data into door objects."""
        return [
            DoorDevice(device_id=device['id'],
                       id=door['id'],
                       index=door['door_index'],
                       serial_number=device['serial_number'],
                       name=door.get('name', 'Garage Door'),
                       manufacturer=device.get('vendor', 'UNKNOWN'),
                       model=MODEL_MAP.get(device.get('model', 'UNKNOWN'), 'UNKNOWN'),
                       has_battery_level=(door.get('battery_level', 0) > 0),
                       ownership=device['ownership'],
                       status=DOOR_STATUS[door.get('status', 'UNKNOWN')],
                       rssi=device.get('rssi', 0),
                       battery_level=door.get('battery_level', 0),
                       fault=bool(door.get('fault')),
                       link_status=DOOR_LINK_STATUS[door.get('link_status', 'UNKNOWN')],
                       ble_strength=device.get('ble_strength', 0))
            for device in data['devices'] for door in device['doors']
            if serial is None or device['serial_number'] == serial
        ]

    @cachedmethod(cache=lambda self: self._cache, key=partial(hashkey, 'cache_all_doors'))
    async def cache_all_doors(self, serial=None):
        """Fetch door data from the service and cache it."""
        headers = {'Authorization': f'Bearer {await self.get_access_token()}'}
        async with self.DOOR_STATUS_LOCK:
            data = await self.fetch_door_data(headers)
            self.log.debug(f'[API] Received response: {json.dumps(data, indent=4, sort_keys=True)}')
            doors = await self.process_door_data(data, serial)
            self._doors = doors
            return doors

    async def open_door(self, door):
        """Open a specified door."""
        return await self.set_door_status(door, DoorStatus.OPEN)

    async def close_door(self, door):
        """Close a specified door."""
        return await self.set_door_status(door, DoorStatus.CLOSED)

    def get_door_status(self, door: DoorDevice) -> DoorStatus:
        """Get the status of a door."""
        try:
            doors = self._doors
            for d in doors:
                if d == door:
                    return door["status"]
        except Exception as ex:
            self.log.error(f"[API] Unknown error in get_door_status(): {ex}")

        return None

    async def set_door_status(self, door, desired_status):
        """Send a command to the service to set a door's status."""
        async with self.DOOR_STATUS_LOCK:
            command = DoorCommand.OPEN if desired_status == DoorStatus.OPEN else DoorCommand.CLOSE
            headers = {'Authorization': f'Bearer {await self.get_access_token()}'}
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
                if self._config.get('logApiResponses', False):
                    self.log.debug(f'[API] Genie {command} response: {data}')

            await self.invalidate_door_cache(door)
            return True

    async def invalidate_door_cache(self, door):
        """Invalidate the cache entry for a specific door."""
        cache_key = self.door_status_cache_key(door)
        if cache_key in self._cache:
            del self._cache[cache_key]
            self.log.debug(f'Cache invalidated for door ID {door.id} at index {door.index}')
        else:
            self.log.debug(f'No cache entry found for door ID {door.id} to invalidate')

    def get_battery_status(self, door: DoorDevice):
        """Get battery status for a door."""
        doors = self._doors
        for d in doors:
            if d == door:
                return door["battery_level"]

    def get_ble_strength(self, door: DoorDevice):
        """Get BLE status for a door."""
        doors = self._doors
        for d in doors:
            if d == door:
                return door["ble_strength"]

    def get_rssi_status(self, door: DoorDevice):
        """Get rssi status for a door."""
        doors = self._doors
        for d in doors:
            if d == door:
                return door["rssi"]

    def get_subscriber_count(self, topic_name:str) -> int:
        """Get subscriber count for a given topic."""
        return self._subscribers_count.get(topic_name, 0)

    def _subscribe_to_topic(self, func: Callable, topic_name: str) -> Listener:
        """Wrap PyPubSub calls to subscribe() to track subscriber count."""
        if topic_name not in self._subscribers_count:
            self._subscribers_count[topic_name] = 0
        self._subscribers_count[topic_name] += 1
        return pub.subscribe(lambda data: func(data), topic_name)

    async def subscribe(self, door: DoorDevice, func: Callable) -> str:
        """Subscribe to status updates for a specific door."""
        topic_name = self.door_status_topic(door)
        isFirstSubscription = self.get_subscriber_count(topic_name) == 0
        listener = self._subscribe_to_topic(lambda data: func(data), topic_name)
        self.log.debug(f'[API] Status subscription added for door {door["name"]} [listener={listener[0].name()}]')

        if isFirstSubscription:
            async def poll():
                if self.get_subscriber_count(topic_name) == 0:
                    self.log.debug('[API] No door status subscriptions; skipping poll')
                    return

                self.log.debug('[API] Polling status for all doors')
                try:
                    doors = await self.get_doors()
                    self.log.debug('[API] Awaiting door statuses')
                    for door in doors:
                        self.log.debug(f'[API] Emitting pubsub message for {door["name"]}')
                        pub.sendMessage(self.door_status_topic(door), door)
                except Exception:
                    # log exception and trap, don't interrupt publish
                    pass

                # Schedule next poll operation
                asyncio.get_running_loop().call_later(
                    self.DOOR_STATUS_POLL_INTERVAL_MS_DEFAULT / 1000,
                    lambda: asyncio.create_task(poll())
                    )

            # immediately start polling
            await asyncio.create_task(poll())

        return listener

    def _unsubscribe_from_topic(self, listener: Listener, topic_name: str):
        """Wrap PyPubSub calls to unsubscribe() to track subscriber count."""
        if topic_name in self._subscribers_count:
            self._subscribers_count[topic_name] -= 1
        if self._subscribers_count[topic_name] == 0:
            del self._subscribers_count[topic_name]
        pub.unsubscribe(listener, topic_name)

    def unsubscribe(self, listener: Listener, door: DoorDevice) -> None:
        """Unsubscribe from door status updates."""
        topic_name = self.door_status_topic(door)
        self._unsubscribe_from_topic(listener, topic_name)
        self.log.debug(f'[API] Status subscription removed for door {door["name"]} [listener={listener[0].name()}]')

    @staticmethod
    def door_status_topic(door):
        """Construct a unique pub/sub topic string based on door information."""
        return f'{AladdinConnect.PUB_SUB_DOOR_STATUS_TOPIC}.{door["device_id"]}.{door["index"]}'

    @staticmethod
    def door_status_cache_key(door):
        """Construct a unique cache key string based on door information."""
        return f'{door["device_id"]}-{door["index"]}'
