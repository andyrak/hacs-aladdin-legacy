"""Models for Aladdin Connect Legacy cover platform."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DoorDevice:
    """Aladdin door device."""

    def __eq__(self, other):
        """Override == operator."""
        if not isinstance(other, DoorDevice):
            return NotImplemented

        return (self.device_id == other.device_id and
                self.index == other.index and
                self.name == other.name and
                self.status == other.status)

    def __hash__(self):
        """Override hash function."""
        return hash((self.device_id, self.index, self.name, self.status))

    battery_level: int
    ble_strength: int
    device_id: str
    fault: bool
    has_battery_level: bool
    has_ble_strength: bool
    id: str
    index: int
    link_status: str
    manufacturer: str
    model: str
    name: str
    ownership: str
    rssi: int
    serial_number: str
    software_version: str
    ssid: str
    status: str
