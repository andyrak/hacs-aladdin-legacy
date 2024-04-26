"""Models for Aladdin Connect Legacy cover platform."""

from __future__ import annotations

from typing import TypedDict


class DoorDevice(TypedDict):
    """Aladdin door device."""

    def __eq__(self, other):
        """Override == operator to check device_id fields."""
        if not isinstance(other, DoorDevice):
            return NotImplemented

        return self.device_id == other.device_id and self.index == other.index

    battery_level: int
    ble_strength: int
    device_id: str
    fault: bool
    has_battery_level: bool
    id: str
    index: int
    link_status: str
    manufacturer: str
    model: str
    name: str
    ownership: str
    rssi: int
    serial_number: str
    status: str
