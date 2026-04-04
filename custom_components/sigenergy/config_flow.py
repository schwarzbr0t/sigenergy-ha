"""Config flow for Sigenergy Cloud integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SigenergyApi, SigenergyAuthError, SigenergyApiError
from .const import (
    AUTH_METHOD_KEY,
    AUTH_METHOD_PASSWORD,
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_AUTH_METHOD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_METHOD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_PASSWORD): vol.In(
            {
                AUTH_METHOD_PASSWORD: "Sigen Account (Username & Password)",
                AUTH_METHOD_KEY: "App Key & Secret",
            }
        ),
    }
)

STEP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APP_KEY): str,
        vol.Required(CONF_APP_SECRET): str,
    }
)


class SigenergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sigenergy Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: choose auth method."""
        if user_input is not None:
            auth_method = user_input[CONF_AUTH_METHOD]
            self.context["auth_method"] = auth_method
            if auth_method == AUTH_METHOD_PASSWORD:
                return await self.async_step_password()
            return await self.async_step_key()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_AUTH_METHOD_SCHEMA,
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle username/password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = SigenergyApi(
                session=session,
                auth_method=AUTH_METHOD_PASSWORD,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            try:
                valid = await api.validate_credentials()
                if not valid:
                    errors["base"] = "invalid_auth"
                else:
                    # Use username as unique ID
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Sigenergy ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_AUTH_METHOD: AUTH_METHOD_PASSWORD,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
            except SigenergyAuthError:
                errors["base"] = "invalid_auth"
            except SigenergyApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during auth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="password",
            data_schema=STEP_PASSWORD_SCHEMA,
            errors=errors,
        )

    async def async_step_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle AppKey/AppSecret authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = SigenergyApi(
                session=session,
                auth_method=AUTH_METHOD_KEY,
                app_key=user_input[CONF_APP_KEY],
                app_secret=user_input[CONF_APP_SECRET],
            )
            try:
                valid = await api.validate_credentials()
                if not valid:
                    errors["base"] = "invalid_auth"
                else:
                    # Use app_key as unique ID
                    await self.async_set_unique_id(user_input[CONF_APP_KEY])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Sigenergy ({user_input[CONF_APP_KEY][:8]}...)",
                        data={
                            CONF_AUTH_METHOD: AUTH_METHOD_KEY,
                            CONF_APP_KEY: user_input[CONF_APP_KEY],
                            CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        },
                    )
            except SigenergyAuthError:
                errors["base"] = "invalid_auth"
            except SigenergyApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during auth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="key",
            data_schema=STEP_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        entry = self._get_reauth_entry()
        auth_method = entry.data.get(CONF_AUTH_METHOD, AUTH_METHOD_PASSWORD)

        if auth_method == AUTH_METHOD_PASSWORD:
            return await self.async_step_password()
        return await self.async_step_key()
