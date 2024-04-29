"""Support for Aladdin Connect Legacy Garage Door sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import AladdinConnect
from .const import DOMAIN
from .model import DoorDevice


@dataclass(frozen=True, kw_only=True)
class AcSensorEntityDescription(SensorEntityDescription):
    """Describes AladdinConnect sensor entity."""

    exists_fn: Callable[[DoorDevice], bool] = lambda _: True
    value_fn: Callable[[DoorDevice], StateType]


SENSORS: tuple[AcSensorEntityDescription, ...] = (
    AcSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda door: door.battery_level,
        exists_fn=lambda door: door.has_battery_level
    ),
    AcSensorEntityDescription(
        key="ble_strength",
        translation_key="ble_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda door: door.ble_strength,
        exists_fn=lambda door: door.has_ble_strength
    ),
    AcSensorEntityDescription(
        key="software_version",
        translation_key="software_version",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda door: door.software_version,
        exists_fn=lambda door: door.software_version != 'UNKNOWN'
    ),
    AcSensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda door: door.ssid,
    ),
    AcSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda door: door.rssi,
    ),

)

async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aladdin Connect sensor devices."""
    ac: AladdinConnect= hass.data[DOMAIN][entry.entry_id]
    doors = await ac.get_doors()

    async_add_entities(
            AladdinConnectSensor(ac, door, description)
            for door in doors for description in SENSORS
            if description.exists_fn(door)
    )


class AladdinConnectSensor(SensorEntity):
    """A sensor implementation for Aladdin Connect devices."""

    entity_description: AcSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        ac: AladdinConnect,
        device: DoorDevice,
        description: AcSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for an Aladdin Connect device."""
        self._ac = ac
        self._door = device
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}-{device.index}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device.device_id}-{device.index}")},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
        )
        self._attr_entity_registry_enabled_default = True


    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return cast(
            float,
            self.entity_description.value_fn(self._door),
        )
