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
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AladdinConnect
from .const import DOMAIN, MODEL_MAP
from .model import DoorDevice


@dataclass(frozen=True, kw_only=True)
class AcSensorEntityDescription(SensorEntityDescription):
    """Describes AladdinConnect sensor entity."""

    value_fn: Callable


SENSORS: tuple[AcSensorEntityDescription, ...] = (
    AcSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=AladdinConnect.get_battery_status,
    ),
    AcSensorEntityDescription(
        key="rssi",
        translation_key="wifi_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=AladdinConnect.get_rssi_status,
    ),
    AcSensorEntityDescription(
        key="ble_strength",
        translation_key="ble_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=AladdinConnect.get_ble_strength,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aladdin Connect sensor devices."""

    ac: AladdinConnect= hass.data[DOMAIN][entry.entry_id]

    entities = []
    doors = await ac.get_doors()

    for door in doors:
        entities.extend(
            [AladdinConnectSensor(ac, door, description) for description in SENSORS]
        )

    async_add_entities(entities)


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
        self._device_id = device["device_id"]
        self._index = device["index"]
        self._ac = ac
        self._door = device
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}-{self._index}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._device_id}-{self._index}")},
            name=device["name"],
            manufacturer=device["manufacturer"],
            model=device["model"],
        )
        if device["model"] == "01" and description.key in (
            "battery_level",
            "ble_strength",
        ):
            self._attr_entity_registry_enabled_default = True

        if device["model"] == MODEL_MAP.get('02') and description.key in (
            "rssi",
        ):
            self._attr_entity_registry_enabled_default = True


    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return cast(
            float,
            self.entity_description.value_fn(self._ac, self._door),
        )
