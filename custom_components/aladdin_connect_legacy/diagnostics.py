"""Diagnostics support for Aladdin Connect Legacy."""

from __future__ import annotations

from typing import Any

from AIOAladdinConnect import AladdinConnectClient

from homeassistant.components.diagnostics import async_redact_data
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"serial", "device_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    acc: AladdinConnectClient = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "doors": async_redact_data(acc.doors, TO_REDACT),
    }
