"""Config flow for Aladdin Connect Legacy cover integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

import voluptuous as vol
from aiohttp.client_exceptions import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import AladdinConnect
from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    config = {
        'username': data[CONF_USERNAME],
        'password': data[CONF_PASSWORD],
    }

    ac = AladdinConnect(logger=_LOGGER, config=config)
    try:
        await ac.init_session()
    except (ClientError, TimeoutError):
        raise

class AladdinConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aladdin Connect."""

    VERSION = 1
    entry: config_entries.ConfigEntry | None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication with Aladdin Connect."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm re-authentication with Aladdin Connect."""
        errors: dict[str, str] = {}

        if user_input:
            assert self.entry is not None
            password = user_input[CONF_PASSWORD]
            data = {
                CONF_USERNAME: self.entry.data[CONF_USERNAME],
                CONF_PASSWORD: password,
            }

            try:
                await validate_input(self.hass, data)

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except (ClientError, TimeoutError):
                errors["base"] = "cannot_connect"

            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"

        except (ClientError, TimeoutError):
            errors["base"] = "cannot_connect"

        else:
            await self.async_set_unique_id(
                user_input["username"].lower(), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Aladdin Connect", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""