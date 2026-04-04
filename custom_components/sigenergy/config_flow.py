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
    CONF_INSTALLATION_ID,
    CONF_REGION,
    DOMAIN,
    REGION_ANZ,
    REGION_AP,
    REGION_CN,
    REGION_EU,
    REGION_JP,
    REGION_LA,
    REGION_MEA,
    REGION_NA,
    REGION_URLS,
)

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_METHOD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION, default=REGION_EU): vol.In(
            {
                REGION_EU: "Europe",
                REGION_AP: "Asia Pacific & Middle Asia",
                REGION_MEA: "Middle East & Africa",
                REGION_CN: "Chinese Mainland",
                REGION_ANZ: "Australia & New Zealand",
                REGION_LA: "Latin America",
                REGION_NA: "North America",
                REGION_JP: "Japan",
            }
        ),
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

STEP_SYSTEM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTALLATION_ID): str,
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
            self.context["region"] = user_input[CONF_REGION]
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
            region = self.context.get("region", REGION_EU)
            base_url = REGION_URLS[region]
            session = async_get_clientsession(self.hass)
            api = SigenergyApi(
                session=session,
                auth_method=AUTH_METHOD_PASSWORD,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                base_url=base_url,
            )
            try:
                valid = await api.validate_credentials()
                if not valid:
                    errors["base"] = "invalid_auth"
                else:
                    self.context["username"] = user_input[CONF_USERNAME]
                    self.context["password"] = user_input[CONF_PASSWORD]
                    return await self.async_step_system()
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
            region = self.context.get("region", REGION_EU)
            base_url = REGION_URLS[region]
            session = async_get_clientsession(self.hass)
            api = SigenergyApi(
                session=session,
                auth_method=AUTH_METHOD_KEY,
                app_key=user_input[CONF_APP_KEY],
                app_secret=user_input[CONF_APP_SECRET],
                base_url=base_url,
            )
            try:
                valid = await api.validate_credentials()
                if not valid:
                    errors["base"] = "invalid_auth"
                else:
                    self.context["app_key"] = user_input[CONF_APP_KEY]
                    self.context["app_secret"] = user_input[CONF_APP_SECRET]
                    return await self.async_step_system()
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

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the installation ID."""
        if user_input is not None:
            installation_id = user_input[CONF_INSTALLATION_ID].strip()
            auth_method = self.context.get("auth_method")
            region = self.context.get("region", REGION_EU)

            if auth_method == AUTH_METHOD_PASSWORD:
                username = self.context["username"]
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Sigenergy ({username})",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_PASSWORD,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: self.context["password"],
                        CONF_REGION: region,
                        CONF_INSTALLATION_ID: installation_id,
                    },
                )

            app_key = self.context["app_key"]
            await self.async_set_unique_id(app_key)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Sigenergy ({app_key[:8]}...)",
                data={
                    CONF_AUTH_METHOD: AUTH_METHOD_KEY,
                    CONF_APP_KEY: app_key,
                    CONF_APP_SECRET: self.context["app_secret"],
                    CONF_REGION: region,
                    CONF_INSTALLATION_ID: installation_id,
                },
            )

        return self.async_show_form(
            step_id="system",
            data_schema=STEP_SYSTEM_SCHEMA,
            description_placeholders={
                "portal_url": "developer.sigencloud.com",
            },
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
