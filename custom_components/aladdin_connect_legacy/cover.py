"""Platform for the Aladdin Connect Legacy cover component."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import homeassistant.helpers.device_registry as dr
from homeassistant import config_entries
from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AladdinConnect
from .const import DOMAIN, STATES_MAP, SUPPORTED_FEATURES
from .model import DoorDevice

SCAN_INTERVAL = timedelta(seconds=300)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aladdin Connect platform."""
    ac: AladdinConnect = hass.data[DOMAIN][config_entry.entry_id]
    doors = await ac.get_doors()
    if doors is None:
        raise PlatformNotReady("Error from Aladdin Connect getting doors")
    async_add_entities(
        (AladdinDevice(ac, door, config_entry) for door in doors),
    )
    remove_stale_devices(hass, config_entry, doors)


def remove_stale_devices(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry, devices: list[dict]
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {f"{door["device_id"]}:{door["index"]}" for door in devices}

    for device_entry in device_entries:
        device_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id is None or device_id not in all_device_ids:
            # If device_id is None an invalid device entry was found for this config entry.
            # If the device_id is not in existing device ids it's a stale device entry.
            # Remove config entry from this device entry in either case.
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )


class AladdinDevice(CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, ac: AladdinConnect, device: DoorDevice, entry: config_entries.ConfigEntry
    ) -> None:
        """Initialize the Aladdin Connect cover."""
        self._ac = ac
        self._device = device
        self._token = ''

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._device["device_id"]}-{self._device["index"]}")},
            name=device["name"],
            manufacturer="Overhead Door",
            model=device["model"],
        )
        self._attr_unique_id = f"{self._device["device_id"]}-{self._device["index"]}"

    async def async_added_to_hass(self) -> None:
        """Connect Aladdin Connect to the cloud."""
        await self._ac.init_session()
        await self._ac.subscribe(self._device, self.async_update)

    async def async_will_remove_from_hass(self) -> None:
        """Close Aladdin Connect before removing."""
        self._ac.unsubscribe(self._token, self._device)
        await self._ac.close_session()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        if not await self._ac.close_door(self._device_id, self._number):
            raise HomeAssistantError("Aladdin Connect API failed to close the cover")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        if not await self._ac.open_door(self._device_id, self._number):
            raise HomeAssistantError("Aladdin Connect API failed to open the cover")

    async def async_update(self, update_info) -> None:
        """Update status of cover."""
        try:
            self._ac.log.debug(f"Recvd update for door: {update_info}")
            self._attr_available = True

        # TODO
        # except (session_manager.ConnectionError, session_manager.InvalidPasswordError):
        #     self._attr_available = False
        except:
            self._attr_available = False

    @property
    def is_closed(self) -> bool | None:
        """Update is closed attribute."""
        value = STATES_MAP.get(self._ac.get_door_status(self._device))
        if value is None:
            return None
        return value == STATE_CLOSED

    @property
    def is_closing(self) -> bool:
        """Update is closing attribute."""
        return (
            STATES_MAP.get(self._ac.get_door_status(self._device))
            == STATE_CLOSING
        )

    @property
    def is_opening(self) -> bool:
        """Update is opening attribute."""
        return (
            STATES_MAP.get(self._ac.get_door_status(self._device))
            == STATE_OPENING
        )
