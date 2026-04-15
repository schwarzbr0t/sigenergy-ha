"""Config flow for Sigenergy Cloud integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SigenergyApi,
    SigenergyApiError,
    SigenergyAuthError,
    SigenergyRateLimitError,
)
from .const import (
    AUTH_METHOD_PASSWORD,
    CONF_AUTH_METHOD,
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

STEP_USER_SCHEMA = vol.Schema(
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
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SigenergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sigenergy Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error_detail": ""}

        if user_input is not None:
            region = user_input[CONF_REGION]
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
                await api.validate_credentials()
            except SigenergyAuthError as err:
                if err.code == 11002:
                    errors["base"] = "user_not_found"
                elif err.code == 11003:
                    errors["base"] = "wrong_password"
                else:
                    errors["base"] = "invalid_auth"
                placeholders["error_detail"] = str(err)
            except SigenergyRateLimitError as err:
                errors["base"] = "rate_limited"
                placeholders["error_detail"] = str(err)
            except SigenergyApiError as err:
                errors["base"] = "cannot_connect"
                placeholders["error_detail"] = str(err)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during auth")
                errors["base"] = "unknown"
                placeholders["error_detail"] = str(err)
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Sigenergy ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_PASSWORD,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REGION: region,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
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
        return await self.async_step_user()
