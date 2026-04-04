"""Select platform for Sigenergy Cloud integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPERATING_MODES
from .coordinator import SigenergyCoordinator

_LOGGER = logging.getLogger(__name__)

# Only modes that can be actively switched to via NBI
SWITCHABLE_MODES = {
    "Maximum Self-Consumption": 0,
    "Fully Feed-in to Grid": 5,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sigenergy select entities from a config entry."""
    coordinator: SigenergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    for system in coordinator.systems:
        system_id = system["systemId"]
        system_name = system.get("systemName", system_id)
        entities.append(
            SigenergyOperatingModeSelect(
                coordinator=coordinator,
                system_id=system_id,
                system_name=system_name,
            )
        )

    async_add_entities(entities)


class SigenergyOperatingModeSelect(
    CoordinatorEntity[SigenergyCoordinator], SelectEntity
):
    """Select entity for switching the operating mode of a Sigenergy system."""

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        system_id: str,
        system_name: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._attr_unique_id = f"{system_id}_operating_mode_select"
        self._attr_name = f"{system_name} Operating Mode Control"
        self._attr_icon = "mdi:cog-transfer"
        self._attr_options = list(SWITCHABLE_MODES.keys())
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def current_option(self) -> str | None:
        """Return the current operating mode."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(
            self._system_id, {}
        )
        mode = system_data.get("operating_mode")
        if mode is not None:
            mode_name = OPERATING_MODES.get(mode)
            if mode_name in SWITCHABLE_MODES:
                return mode_name
        return None

    async def async_select_option(self, option: str) -> None:
        """Switch to the selected operating mode."""
        mode_value = SWITCHABLE_MODES.get(option)
        if mode_value is None:
            _LOGGER.error("Unknown operating mode: %s", option)
            return

        _LOGGER.info(
            "Switching system %s to operating mode: %s (%s)",
            self._system_id,
            option,
            mode_value,
        )
        await self.coordinator.api.set_operating_mode(self._system_id, mode_value)
        await self.coordinator.async_request_refresh()
