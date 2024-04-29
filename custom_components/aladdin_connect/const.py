"""Platform for the Aladdin Connect Legacy cover component."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING


class DoorStatus(StrEnum):
    """Aladdin Connect door status."""

    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    UNKNOWN = "unknown"
    TIMEOUT_CLOSE = "open"  # If it timed out opening, it's still closed?
    TIMEOUT_OPEN = "closed"  # If it timed out closing, it's still open?
    CONNECTED = "Connected"
    NOT_CONFIGURED = "NotConfigured"

class DoorCommand(StrEnum):
    """Aladdin Connect Door commands."""

    CLOSE = "CLOSE_DOOR"
    OPEN = "OPEN_DOOR"

DOMAIN = "aladdin_connect"
NOTIFICATION_ID: Final = "aladdin_notification"
NOTIFICATION_TITLE: Final = "Aladdin Connect Cover Setup"
SUPPORTED_FEATURES: Final = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

STATES_MAP: Final[dict[str, str]] = {
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
}

MODEL_MAP: Final[dict[str, str]] = {
    "02": "Ceiling Mount (02)",
}

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
