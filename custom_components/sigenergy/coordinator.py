"""DataUpdateCoordinator for Sigenergy Cloud."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import SigenergyApi, SigenergyApiError, SigenergyAuthError
from .const import (
    API_BASE_URL,
    AUTH_METHOD_KEY,
    AUTH_METHOD_PASSWORD,
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_AUTH_METHOD,
    CONF_INSTALLATION_ID,
    CONF_REGION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REGION_URLS,
)

_LOGGER = logging.getLogger(__name__)

class SigenergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Sigenergy data from the cloud API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.api = self._create_api(hass, entry)
        self.systems: list[dict[str, Any]] = []
        self.devices: dict[str, list[dict[str, Any]]] = {}

    @staticmethod
    def _create_api(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> SigenergyApi:
        """Create API client from config entry."""
        session = async_get_clientsession(hass)
        auth_method = entry.data.get(CONF_AUTH_METHOD, AUTH_METHOD_PASSWORD)

        region = entry.data.get(CONF_REGION)
        base_url = REGION_URLS.get(region, API_BASE_URL)

        if auth_method == AUTH_METHOD_PASSWORD:
            return SigenergyApi(
                session=session,
                auth_method=AUTH_METHOD_PASSWORD,
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                base_url=base_url,
            )
        return SigenergyApi(
            session=session,
            auth_method=AUTH_METHOD_KEY,
            app_key=entry.data[CONF_APP_KEY],
            app_secret=entry.data[CONF_APP_SECRET],
            base_url=base_url,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator: build system list and fetch devices."""
        installation_id = self.config_entry.data.get(CONF_INSTALLATION_ID)
        try:
            if installation_id:
                self.systems = [{"systemId": installation_id}]
            else:
                self.systems = await self.api.get_system_list()
            for system in self.systems:
                system_id = system["systemId"]
                self.devices[system_id] = await self.api.get_device_list(system_id)
        except SigenergyAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except SigenergyApiError as err:
            raise UpdateFailed(f"Error fetching system list: {err}") from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Sigenergy API."""
        try:
            result: dict[str, Any] = {"systems": {}}

            for system in self.systems:
                system_id = system["systemId"]
                system_data: dict[str, Any] = {
                    "info": system,
                    "summary": {},
                    "energy_flow": {},
                    "operating_mode": None,
                    "devices": {},
                }

                # Fetch system-level realtime data
                try:
                    system_data["summary"] = await self.api.get_realtime_summary(
                        system_id
                    )
                except SigenergyApiError as err:
                    _LOGGER.debug("Error fetching summary for %s: %s", system_id, err)

                try:
                    system_data["energy_flow"] = await self.api.get_energy_flow(
                        system_id
                    )
                except SigenergyApiError as err:
                    _LOGGER.debug(
                        "Error fetching energy flow for %s: %s", system_id, err
                    )

                # Fetch operating mode
                try:
                    system_data["operating_mode"] = await self.api.get_operating_mode(
                        system_id
                    )
                except SigenergyApiError as err:
                    _LOGGER.debug(
                        "Error fetching operating mode for %s: %s", system_id, err
                    )

                # Fetch device-level realtime data
                devices = self.devices.get(system_id, [])
                for device in devices:
                    serial = device.get("serialNumber", "")
                    try:
                        device_data = await self.api.get_device_realtime(
                            system_id, serial
                        )
                        system_data["devices"][serial] = {
                            "info": device,
                            "realtime": device_data.get("realTimeInfo", {}),
                        }
                    except SigenergyApiError as err:
                        _LOGGER.debug(
                            "Error fetching device %s data: %s", serial, err
                        )

                result["systems"][system_id] = system_data

            return result

        except SigenergyAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except SigenergyApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
