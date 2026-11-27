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

    async def _async_validate(
        self, region: str, username: str, password: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Validate credentials; return (errors, description placeholders)."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error_detail": ""}
        api = SigenergyApi(
            session=async_get_clientsession(self.hass),
            auth_method=AUTH_METHOD_PASSWORD,
            username=username,
            password=password,
            base_url=REGION_URLS[region],
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
        return errors, placeholders

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error_detail": ""}

        if user_input is not None:
            region = user_input[CONF_REGION]
            errors, placeholders = await self._async_validate(
                region, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
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
        """Ask for the new password and store it on the existing entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {
            "error_detail": "",
            CONF_USERNAME: entry.data[CONF_USERNAME],
        }

        if user_input is not None:
            errors, detail = await self._async_validate(
                entry.data[CONF_REGION],
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            placeholders.update(detail)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders=placeholders,
        )
