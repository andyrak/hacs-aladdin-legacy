"""Platform for the Aladdin Connect Legacy cover component."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

CLIENT_ID = "1000"
DOMAIN = "aladdin_connect_legacy"
NOTIFICATION_ID: Final = "aladdin_notification"
NOTIFICATION_TITLE: Final = "Aladdin Connect Cover Setup"
SUPPORTED_FEATURES: Final = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

STATES_MAP: Final[dict[str, str]] = {
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
}

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
