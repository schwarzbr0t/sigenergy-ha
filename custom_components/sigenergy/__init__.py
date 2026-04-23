"""The Sigenergy Cloud integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CONF_CACHED_DEVICES, CONF_CACHED_SYSTEMS, DOMAIN
from .coordinator import SigenergyCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT]

SERVICE_REFRESH_SYSTEMS = "refresh_systems"
SERVICE_REFRESH_SYSTEMS_SCHEMA = vol.Schema(
    {vol.Optional("entry_id"): cv.string}
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
