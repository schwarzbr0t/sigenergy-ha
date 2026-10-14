"""The Sigenergy Cloud integration."""
from __future__ import annotations

import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .backfill import async_plan_backfill
from .const import (
    CONF_CACHED_DEVICES,
    CONF_CACHED_SYSTEMS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import SigenergyCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT]

SERVICE_REFRESH_SYSTEMS = "refresh_systems"
SERVICE_REFRESH_SYSTEMS_SCHEMA = vol.Schema(
    {vol.Optional("entry_id"): cv.string}
)

SERVICE_BACKFILL_STATISTICS = "backfill_statistics"
SERVICE_BACKFILL_STATISTICS_SCHEMA = vol.Schema(
    {
        vol.Optional("system_id"): cv.string,
        vol.Required("start_date"): cv.date,
        vol.Required("end_date"): cv.date,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sigenergy Cloud from a config entry."""
    coordinator = SigenergyCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_SYSTEMS)
            hass.services.async_remove(DOMAIN, SERVICE_BACKFILL_STATISTICS)
    return unload_ok


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_SYSTEMS):
        return

    async def _handle_refresh_systems(call: ServiceCall) -> None:
        """Clear the cached system/device list and reload.

        Forces the coordinator to re-query the Sigenergy API for systems
        linked to the account — picks up newly-added systems that would
        otherwise remain invisible behind the cache.
        """
        target_entry_id = call.data.get("entry_id")
        entries = hass.config_entries.async_entries(DOMAIN)
        if target_entry_id:
            entries = [e for e in entries if e.entry_id == target_entry_id]
            if not entries:
                _LOGGER.warning(
                    "No Sigenergy config entry with entry_id=%s", target_entry_id
                )
                return

        for entry in entries:
            new_data = {
                k: v
                for k, v in entry.data.items()
                if k not in (CONF_CACHED_SYSTEMS, CONF_CACHED_DEVICES)
            }
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info(
                "Cleared cached systems/devices for %s — reloading", entry.title
            )
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_SYSTEMS,
        _handle_refresh_systems,
        schema=SERVICE_REFRESH_SYSTEMS_SCHEMA,
    )

    async def _handle_backfill_statistics(call: ServiceCall) -> ServiceResponse:
        """Import daily history from the Sigenergy Cloud into statistics.

        Only plans the backfill: the coordinator fetches one month per
        history request, alternating with the history sensors, so the
        endpoint's rate limit (one request per station every 5 minutes)
        is respected.
        """
        system_id: str | None = call.data.get("system_id")
        start: datetime.date = call.data["start_date"]
        # Today is incomplete and is covered by the live sensors
        end: datetime.date = min(
            call.data["end_date"],
            dt_util.now().date() - datetime.timedelta(days=1),
        )
        if start > end:
            raise ServiceValidationError(
                "start_date must be on or before end_date, and before today"
            )

        selected: list[tuple[SigenergyCoordinator, str]] = [
            (coordinator, system["systemId"])
            for coordinator in hass.data.get(DOMAIN, {}).values()
            for system in coordinator.systems
            if system_id in (None, system["systemId"])
        ]
        if not selected:
            raise ServiceValidationError(
                f"No loaded Sigenergy system with system_id {system_id}"
            )
        for coordinator, sid in selected:
            if sid in coordinator.backfill_jobs:
                raise ServiceValidationError(
                    f"A statistics backfill for {sid} is already running"
                )

        response: dict[str, Any] = {}
        for coordinator, sid in selected:
            job = await async_plan_backfill(hass, sid, start, end)
            if not job.done:
                coordinator.async_start_backfill(job)
                _LOGGER.info(
                    "Statistics backfill for %s queued: %d month(s) for %s",
                    sid,
                    len(job.months),
                    ", ".join(t.statistic_id for t in job.targets),
                )
            else:
                _LOGGER.info(
                    "Statistics backfill for %s: nothing to import between %s and %s",
                    sid, start, end,
                )
            response[sid] = {
                "months": len(job.months),
                # Every other poll is a backfill request
                "estimated_minutes": len(job.months) * 2 * DEFAULT_SCAN_INTERVAL // 60,
                "statistics": {
                    t.statistic_id: {
                        "start_date": t.first_day.isoformat(),
                        "end_date": t.last_day.isoformat(),
                    }
                    for t in job.targets
                },
            }
        return response

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKFILL_STATISTICS,
        _handle_backfill_statistics,
        schema=SERVICE_BACKFILL_STATISTICS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
