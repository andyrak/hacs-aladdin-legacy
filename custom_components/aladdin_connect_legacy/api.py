"""API setup for Aladdin Connect."""

import base64
import hmac
from collections.abc import Callable
from functools import partial

import aiohttp
from cachetools import TTLCache, cachedmethod
from cachetools.keys import hashkey
from pubsub import pub

from .const import DoorCommand, DoorStatus
from .model import DoorDevice


class AladdinConnect:
    PUB_SUB_DOOR_STATUS_TOPIC = 'door'
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_DEFAULT = 15
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_MIN = 5
    DOOR_STATUS_STATIONARY_CACHE_TTL_S_MAX = 60
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_DEFAULT = 5
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MIN = 1
    DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MAX = 30
    DOOR_STATUS_POLL_INTERVAL_MS_DEFAULT = 15000
    DOOR_STATUS_POLL_INTERVAL_MS_MIN = 5000
    DOOR_STATUS_POLL_INTERVAL_MS_MAX = 60000
    API_HOST = 'api.smartgarage.systems'
    API_TIMEOUT = 5000
    AUTH_HOST = 'cognito-idp.us-east-2.amazonaws.com'
    AUTH_CLIENT_ID = '27iic8c3bvslqngl3hso83t74b'
    AUTH_CLIENT_SECRET = '7bokto0ep96055k42fnrmuth84k7jdcjablestb7j53o8lp63v5'

    DOOR_STATUS = {
        0: DoorStatus.UNKNOWN,  # Unknown
        1: DoorStatus.OPEN,  # open
        2: DoorStatus.OPENING,  # opening
        3: DoorStatus.TIMEOUT_OPEN,  # Timeout Opening
        4: DoorStatus.CLOSED,  # closed
        5: DoorStatus.CLOSING,  # closing
        6: DoorStatus.TIMEOUT_CLOSE,  # Timeout Closing
        7: DoorStatus.UNKNOWN,  # Not Configured
    }

    REQUEST_DOOR_STATUS_COMMAND = {
        DoorStatus.CLOSED: DoorCommand.CLOSE,
        DoorStatus.OPEN: DoorCommand.OPEN,
    }

    DOOR_LINK_STATUS = {
        0: "Unknown",
        1: DoorStatus.NOT_CONFIGURED,
        2: "Paired",
        3: DoorStatus.CONNECTED,
    }

    DEVICE_FAULT = {
        0: "None",
        1: "UL lockout",
        2: "Interlock",
        3: "Not safe",
        4: "Will not move",
    }

    DEVICE_STATUS = {
        0: "Offline",
        1: DoorStatus.CONNECTED,
    }

    def __init__(self, logger, config):
        self.cache = TTLCache(maxsize=1024, ttl=3600)  # Example settings
        self.config = config
        self.doors: list[DoorDevice] = []
        self.log = logger
        self.session = None  # Will be set in the async context


    async def get_access_token(self, encoding='utf-8'):
        digest = hmac.new(self.AUTH_CLIENT_SECRET.encode(encoding), (self.config['username'] + self.AUTH_CLIENT_ID).encode(encoding), 'sha256').digest()
        digest_b64 = base64.b64encode(digest)
        secret_hash = digest_b64.decode(encoding)
        async with self.session.post(f'https://{self.AUTH_HOST}', json={
            'ClientId': self.AUTH_CLIENT_ID,
            'AuthFlow': 'USER_PASSWORD_AUTH',
            'AuthParameters': {
                'USERNAME': self.config['username'],
                'PASSWORD': self.config['password'],
                'SECRET_HASH': secret_hash,
            },
        }, headers={'Content-Type': 'application/x-amz-json-1.1', 'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'}) as response:
            response.raise_for_status()
            data = await response.json(content_type='application/x-amz-json-1.1')
            return data['AuthenticationResult']['AccessToken']

    async def get_doors(self, serial: str = None):
        self._doors = self.cache_all_doors()
        return await self._doors

    @cachedmethod(cache=lambda self: TTLCache(maxsize=1024, ttl=300), key=partial(hashkey, 'getAllDoors'))
    async def cache_all_doors(self) -> list[DoorDevice]:
        headers = {
            'Authorization': f'Bearer {await self.get_access_token()}'
        }
        async with self.session.get(f'https://{self.API_HOST}/devices', headers=headers) as response:
            if response.status != 200:
                error_message = await response.text()
                self.log.error(f'[API] An error occurred getting devices from account; {error_message}')
                response.raise_for_status()

            data = await response.json()

            if self.config.get('logApiResponses', False):
                self.log.debug(f'[API] Configuration response: {data}')

            doors: list[DoorDevice] = []
            for device in data['devices']:
                for door in device['doors']:
                    door_data: DoorDevice = {
                        'device_id': device['id'],
                        'id': door['id'],
                        'index': door['door_index'],
                        'serial_number': device['serial_number'],
                        'name': door.get('name', 'Garage Door'),
                        'model': door.get('model', 'UNKNOWN'),
                        'has_battery_level': (door.get('battery_level', 0) > 0),
                        'ownership': device['ownership'],
                        'status': self.DOOR_STATUS[door.get('status', 0)],
                        'rssi': device.get("rssi", 0),
                        'battery_level': door.get('battery_level', 0),
                        'fault': bool(door.get('fault')),
                        'link_status': self.DOOR_LINK_STATUS[door.get("link_status", 0)],
                        'ble_strength': device.get('ble_strength', 0)
                    }
                    doors.append(door_data)

            return doors

    async def close_door(self, door: DoorDevice):
        """Command to close the door."""
        return await self.set_door_status(door, DoorStatus.CLOSED)

    async def open_door(self, door: DoorDevice):
        """Command to open the door."""
        return await self.set_door_status(door, DoorStatus.OPEN)

    async def get_door_status(self, door: DoorDevice) -> DoorStatus:
        """Async call to get the status of a door."""
        doors = self.get_doors()
        for d in doors:
            if d == door:
                return door["status"]
        return None

    async def set_door_status(self, door: DoorDevice, desired_status: DoorStatus) -> None:
        """Async call to set the status of a door device."""
        command = DoorCommand.OPEN if desired_status == DoorStatus.OPEN else DoorCommand.CLOSE
        headers = {'Authorization': f'Bearer {await self.get_access_token()}'}
        try:
            async with self.session.post(
                f'https://{self.API_HOST}/command/devices/{door["device_id"]}/doors/{door["index"]}',
                json={'command': command},
                headers=headers
            ) as response:
                if response.status != 200:
                    error_message = await response.text()
                    self.log.error(f'[API] An error occurred sending command {command} to door {door["name"]}; {error_message}')
                    response.raise_for_status()

                data = await response.json()
                if self.config.get('logApiResponses', False):
                    self.log.debug(f'[API] Genie {command} response: {data}')

        except Exception as error:
            self.log.error(f'[API] An error occurred sending command {command} to door {door["name"]}; {error}')
            raise

        await self.invalidate_door_cache(door)

    def get_battery_status(self, door: DoorDevice):
        """Get battery status for a door."""
        doors = self.get_doors()
        for d in doors:
            if d == door:
                return door["battery_level"]

    def get_rssi_status(self, door: DoorDevice):
        """Get rssi status for a door."""
        doors = self.get_doors()
        for d in doors:
            if d == door:
                return door["rssi"]

    def get_ble_strength(self, door: DoorDevice):
        """Get BLE status for a door."""
        doors = self.get_doors()
        for d in doors:
            if d == door:
                return door["ble_strength"]

    async def invalidate_door_cache(self, door: DoorDevice) -> None:
        """Invalidate the cache for a specific door."""
        cache_key = self.door_status_cache_key(door)
        if cache_key in self.cache:
            del self.cache[cache_key]
            self.log.debug(f'Cache invalidated for door ID {door["id"]} at index {door["index"]}')
        else:
            self.log.debug(f'No cache entry found for door ID {door["id"]} to invalidate')

    async def subscribe(self, door: DoorDevice, func: Callable) -> str:
        """Subscribe to status updates for a specific door."""
        topic = self.door_status_topic(door)
        token = pub.subscribe(lambda data: func(data), topic)
        self.log.debug(f'[API] Status subscription added for door {door["name"]} [token={token}]')
        return token

    def unsubscribe(self, token: str, door: DoorDevice) -> None:
        """Unsubscribe from door status updates."""
        topic = self.door_status_topic(door)
        pub.unsubscribe(token, topic)
        self.log.debug(f'[API] Status subscription removed for token {token}')

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    def door_status_stationary_cache_ttl(self):
        # Computes TTL for stationary door status, with bounds checking
        return max(
            self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_MIN,
            min(
                self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_MAX,
                self.config.get('doorStatusStationaryCacheTtl', self.DOOR_STATUS_STATIONARY_CACHE_TTL_S_DEFAULT)
            )
        )

    def door_status_transitioning_cache_ttl(self):
        # Computes TTL for transitioning door status, with bounds checking
        return max(
            self.DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MIN,
            min(
                self.DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_MAX,
                self.config.get('doorStatusTransitioningCacheTtl', self.DOOR_STATUS_TRANSITIONING_CACHE_TTL_S_DEFAULT)
            )
        )

    def poll_interval_ms(self):
        # Computes the polling interval in milliseconds, with bounds checking
        return max(
            self.DOOR_STATUS_POLL_INTERVAL_MS_MIN,
            min(
                self.DOOR_STATUS_POLL_INTERVAL_MS_MAX,
                self.config.get('doorStatusPollInterval', self.DOOR_STATUS_POLL_INTERVAL_MS_DEFAULT)
            )
        )

    @staticmethod
    def door_status_topic(door: DoorDevice) -> str:
        """Construct a unique pub/sub topic string based on door information."""
        return f'{AladdinConnect.PUB_SUB_DOOR_STATUS_TOPIC}.{door["device_id"]}.{door["index"]}'

    @staticmethod
    def door_status_cache_key(door: DoorDevice) -> str:
        """Construct a unique cache key string based on door information."""
        return f'{door["device_id"]}:{door["index"]}'
