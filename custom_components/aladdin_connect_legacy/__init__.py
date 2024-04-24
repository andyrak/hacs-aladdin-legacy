"""The aladdin_legacy_connect component."""
import logging
from typing import Final

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import AladdinConnect
from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up platform from a config_entries.ConfigEntry."""
    config = {
        'username': entry.data[CONF_USERNAME],
        'password': entry.data[CONF_PASSWORD]
    }

    ac = AladdinConnect(_LOGGER, config)

    try:
        await ac.init_session()
    except (TimeoutError) as ex:
        raise ConfigEntryNotReady("Can not connect to host") from ex
    except:
        # TODO proper exceptions
        raise ConfigEntryAuthFailed("Incorrect Password") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ac
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
