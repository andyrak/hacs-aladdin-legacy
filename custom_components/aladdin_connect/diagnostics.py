"""Diagnostics support for Aladdin Connect Legacy."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .api import AladdinConnect
from .const import DOMAIN

TO_REDACT = {"serial_number", "device_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    ac: AladdinConnect = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "doors": async_redact_data(ac.get_doors(), TO_REDACT),
    }
