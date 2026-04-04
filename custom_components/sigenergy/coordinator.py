"""DataUpdateCoordinator for Sigenergy Cloud."""
from __future__ import annotations

from datetime import timedelta
import datetime
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

from .api import SigenergyApi, SigenergyApiError, SigenergyAuthError, SigenergyRateLimitError
from .const import (
    API_BASE_URL,
    AUTH_METHOD_KEY,
    AUTH_METHOD_PASSWORD,
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_AUTH_METHOD,
    CONF_CACHED_DEVICES,
    CONF_CACHED_SYSTEMS,
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
        cached_systems = self.config_entry.data.get(CONF_CACHED_SYSTEMS)
        cached_devices = self.config_entry.data.get(CONF_CACHED_DEVICES, {})

        try:
            if installation_id:
                self.systems = [{"systemId": installation_id}]
            elif cached_systems:
                self.systems = cached_systems
                _LOGGER.debug(
                    "Using cached system list (%d system(s)) — skipping API call",
                    len(self.systems),
                )
            else:
                self.systems = await self.api.get_system_list()

            new_cached_devices: dict[str, Any] = dict(cached_devices)
            data_changed = not cached_systems

            for system in self.systems:
                system_id = system["systemId"]
                if system_id in cached_devices:
                    self.devices[system_id] = cached_devices[system_id]
                    _LOGGER.debug(
                        "Using cached device list for system %s", system_id
                    )
                else:
                    self.devices[system_id] = await self.api.get_device_list(system_id)
                    new_cached_devices[system_id] = self.devices[system_id]
                    data_changed = True

            if data_changed:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_CACHED_SYSTEMS: self.systems,
                        CONF_CACHED_DEVICES: new_cached_devices,
                    },
                )

        except SigenergyRateLimitError as err:
            if cached_systems:
                # Rate limited but we have a cache — use it and continue
                _LOGGER.warning(
                    "Sigenergy API rate limit hit during setup, using cached data: %s", err
                )
                self.systems = cached_systems
                self.devices = {k: v for k, v in cached_devices.items()}
            else:
                raise UpdateFailed(
                    "Sigenergy API rate limit reached (max 1 request/5 min for system list). "
                    "Home Assistant will retry automatically — usually within a few minutes."
                ) from err
        except SigenergyAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Please check your credentials under "
                "Settings → Devices & Services → Sigenergy Cloud → Reconfigure."
            ) from err
        except SigenergyApiError as err:
            raise UpdateFailed(
                f"Could not connect to the Sigenergy API: {err}"
            ) from err

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

            result["last_updated"] = datetime.datetime.now(datetime.timezone.utc)
            return result

        except SigenergyAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Please check your credentials under "
                "Settings → Devices & Services → Sigenergy Cloud → Reconfigure."
            ) from err
        except SigenergyRateLimitError as err:
            raise UpdateFailed(
                "Sigenergy API rate limit reached. Data will refresh automatically "
                "in the next polling cycle (every 5 minutes)."
            ) from err
        except SigenergyApiError as err:
            raise UpdateFailed(f"Could not connect to the Sigenergy API: {err}") from err
