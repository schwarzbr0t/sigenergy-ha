"""Sensor platform for Sigenergy Cloud integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_TYPE_INVERTER,
    DEVICE_TYPE_BATTERY,
    DEVICE_TYPE_GATEWAY,
    DEVICE_TYPE_METER,
    DOMAIN,
    OPERATING_MODES,
)
from .coordinator import SigenergyCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SigenergySensorDescription(SensorEntityDescription):
    """Describe a Sigenergy sensor."""

    value_fn: str  # Key path in the data dict


# ── System-level energy flow sensors ────────────────────────────

SYSTEM_ENERGY_FLOW_SENSORS: tuple[SigenergySensorDescription, ...] = (
    SigenergySensorDescription(
        key="pv_power",
        translation_key="pv_power",
        name="PV Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="pvPower",
    ),
    SigenergySensorDescription(
        key="grid_power",
        translation_key="grid_power",
        name="Grid Power",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="gridPower",
    ),
    SigenergySensorDescription(
        key="battery_power",
        translation_key="battery_power",
        name="Battery Power",
        icon="mdi:battery-charging",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="batteryPower",
    ),
    SigenergySensorDescription(
        key="load_power",
        translation_key="load_power",
        name="Load Power",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="loadPower",
    ),
    SigenergySensorDescription(
        key="ev_power",
        translation_key="ev_power",
        name="EV Charger Power",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="evPower",
    ),
    SigenergySensorDescription(
        key="heat_pump_power",
        translation_key="heat_pump_power",
        name="Heat Pump Power",
        icon="mdi:heat-pump",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="heatPumpPower",
    ),
    SigenergySensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        name="Battery State of Charge",
        icon="mdi:battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="batterySoc",
    ),
)

# ── System summary sensors ──────────────────────────────────────

SYSTEM_SUMMARY_SENSORS: tuple[SigenergySensorDescription, ...] = (
    SigenergySensorDescription(
        key="daily_generation",
        translation_key="daily_generation",
        name="Daily PV Generation",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="dailyPowerGeneration",
    ),
    SigenergySensorDescription(
        key="monthly_generation",
        translation_key="monthly_generation",
        name="Monthly PV Generation",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="monthlyPowerGeneration",
    ),
    SigenergySensorDescription(
        key="annual_generation",
        translation_key="annual_generation",
        name="Annual PV Generation",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="annualPowerGeneration",
    ),
    SigenergySensorDescription(
        key="lifetime_generation",
        translation_key="lifetime_generation",
        name="Lifetime PV Generation",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="lifetimePowerGeneration",
    ),
)

# ── Inverter device sensors ─────────────────────────────────────

INVERTER_SENSORS: tuple[SigenergySensorDescription, ...] = (
    SigenergySensorDescription(
        key="active_power",
        name="Active Power",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="activePower",
    ),
    SigenergySensorDescription(
        key="pv_power",
        name="PV Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="pvPower",
    ),
    SigenergySensorDescription(
        key="bat_power",
        name="Battery Power",
        icon="mdi:battery-charging",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="batPower",
    ),
    SigenergySensorDescription(
        key="bat_soc",
        name="Battery SOC",
        icon="mdi:battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="batSoc",
    ),
    SigenergySensorDescription(
        key="grid_frequency",
        name="Grid Frequency",
        icon="mdi:sine-wave",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="gridFrequency",
    ),
    SigenergySensorDescription(
        key="internal_temp",
        name="Internal Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="internalTemperature",
    ),
    SigenergySensorDescription(
        key="phase_a_voltage",
        name="Phase A Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="aPhaseVoltage",
    ),
    SigenergySensorDescription(
        key="phase_b_voltage",
        name="Phase B Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="bPhaseVoltage",
    ),
    SigenergySensorDescription(
        key="phase_c_voltage",
        name="Phase C Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="cPhaseVoltage",
    ),
    SigenergySensorDescription(
        key="phase_a_current",
        name="Phase A Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="aPhaseCurrent",
    ),
    SigenergySensorDescription(
        key="phase_b_current",
        name="Phase B Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="bPhaseCurrent",
    ),
    SigenergySensorDescription(
        key="phase_c_current",
        name="Phase C Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="cPhaseCurrent",
    ),
    SigenergySensorDescription(
        key="power_factor",
        name="Power Factor",
        icon="mdi:angle-acute",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value_fn="powerFactor",
    ),
    SigenergySensorDescription(
        key="pv_energy_daily",
        name="PV Energy Daily",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="pvEnergyDaily",
    ),
    SigenergySensorDescription(
        key="pv_energy_total",
        name="PV Energy Total",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="pvEnergyTotal",
    ),
    SigenergySensorDescription(
        key="es_charging_day",
        name="Battery Charging Today",
        icon="mdi:battery-arrow-up",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="esChargingDay",
    ),
    SigenergySensorDescription(
        key="es_discharging_day",
        name="Battery Discharging Today",
        icon="mdi:battery-arrow-down",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="esDischargingDay",
    ),
    SigenergySensorDescription(
        key="es_discharging_total",
        name="Battery Discharging Total",
        icon="mdi:battery-arrow-down",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn="esDischargingTotal",
    ),
)

# ── Meter sensors ───────────────────────────────────────────────

METER_SENSORS: tuple[SigenergySensorDescription, ...] = (
    SigenergySensorDescription(
        key="active_power",
        name="Active Power",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="activePower",
    ),
    SigenergySensorDescription(
        key="voltage_a",
        name="Phase A Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="voltageA",
    ),
    SigenergySensorDescription(
        key="voltage_b",
        name="Phase B Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="voltageB",
    ),
    SigenergySensorDescription(
        key="voltage_c",
        name="Phase C Voltage",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="voltageC",
    ),
    SigenergySensorDescription(
        key="current_a",
        name="Phase A Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="currentA",
    ),
    SigenergySensorDescription(
        key="current_b",
        name="Phase B Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="currentB",
    ),
    SigenergySensorDescription(
        key="current_c",
        name="Phase C Current",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="currentC",
    ),
    SigenergySensorDescription(
        key="grid_frequency",
        name="Grid Frequency",
        icon="mdi:sine-wave",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn="gridFrequency",
    ),
    SigenergySensorDescription(
        key="power_factor",
        name="Power Factor",
        icon="mdi:angle-acute",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
        value_fn="powerFactor",
    ),
)


def _get_sensors_for_device_type(
    device_type: str,
) -> tuple[SigenergySensorDescription, ...]:
    """Return sensor descriptions for a given device type."""
    if device_type == DEVICE_TYPE_INVERTER:
        return INVERTER_SENSORS
    if device_type == DEVICE_TYPE_METER:
        return METER_SENSORS
    # Gateway and Battery have limited realtime fields, reuse subset
    if device_type == DEVICE_TYPE_GATEWAY:
        return METER_SENSORS[:8]  # Voltage, current, active/reactive power
    return ()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sigenergy sensors from a config entry."""
    coordinator: SigenergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for system in coordinator.systems:
        system_id = system["systemId"]
        system_name = system.get("systemName", system_id)

        # System-level energy flow sensors
        for desc in SYSTEM_ENERGY_FLOW_SENSORS:
            entities.append(
                SigenergySystemSensor(
                    coordinator=coordinator,
                    description=desc,
                    system_id=system_id,
                    system_name=system_name,
                    data_source="energy_flow",
                )
            )

        # System-level summary sensors
        for desc in SYSTEM_SUMMARY_SENSORS:
            entities.append(
                SigenergySystemSensor(
                    coordinator=coordinator,
                    description=desc,
                    system_id=system_id,
                    system_name=system_name,
                    data_source="summary",
                )
            )

        # Operating mode as a sensor
        entities.append(
            SigenergyOperatingModeSensor(
                coordinator=coordinator,
                system_id=system_id,
                system_name=system_name,
            )
        )

        # Battery capacity and stored energy sensors
        entities.append(
            SigenergyBatteryCapacitySensor(
                coordinator=coordinator,
                system_id=system_id,
                system_name=system_name,
            )
        )
        entities.append(
            SigenergyBatteryEnergySensor(
                coordinator=coordinator,
                system_id=system_id,
                system_name=system_name,
            )
        )

        # Last sync / next sync diagnostic sensors
        entities.append(
            SigenergyLastSyncSensor(
                coordinator=coordinator,
                system_id=system_id,
                system_name=system_name,
            )
        )

        # Device-level sensors
        devices = coordinator.devices.get(system_id, [])
        for device in devices:
            serial = device.get("serialNumber", "")
            device_type = device.get("deviceType", "")
            device_name = f"{system_name} {device_type} {serial[-4:]}"
            sensor_descs = _get_sensors_for_device_type(device_type)

            for desc in sensor_descs:
                entities.append(
                    SigenergyDeviceSensor(
                        coordinator=coordinator,
                        description=desc,
                        system_id=system_id,
                        serial_number=serial,
                        device_type=device_type,
                        device_name=device_name,
                    )
                )

    async_add_entities(entities)


class SigenergySystemSensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Sensor for system-level Sigenergy data."""

    entity_description: SigenergySensorDescription

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        description: SigenergySensorDescription,
        system_id: str,
        system_name: str,
        data_source: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._system_id = system_id
        self._data_source = data_source
        self._attr_unique_id = f"{system_id}_{data_source}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(
            self._system_id, {}
        )
        source_data = system_data.get(self._data_source, {})
        value = source_data.get(self.entity_description.value_fn)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        return None


class SigenergyOperatingModeSensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Sensor for the current operating mode of a system."""

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        system_id: str,
        system_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._attr_unique_id = f"{system_id}_operating_mode"
        self._attr_name = "Operating Mode"
        self._attr_icon = "mdi:cog"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def native_value(self) -> str | None:
        """Return the current operating mode name."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(
            self._system_id, {}
        )
        mode = system_data.get("operating_mode")
        if mode is not None:
            return OPERATING_MODES.get(mode, f"Unknown ({mode})")
        return None


class SigenergyBatteryCapacitySensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Sensor showing total rated battery capacity in kWh."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"
    _attr_entity_category = "diagnostic"

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        system_id: str,
        system_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._attr_unique_id = f"{system_id}_battery_capacity_kwh"
        self._attr_name = "Battery Total Capacity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def native_value(self) -> float | None:
        """Return total battery capacity in kWh."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(self._system_id, {})
        capacity = system_data.get("info", {}).get("batteryCapacity")
        try:
            return float(capacity) if capacity is not None else None
        except (ValueError, TypeError):
            return None


class SigenergyBatteryEnergySensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Computed sensor: battery stored energy in kWh (capacity × SOC)."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery-high"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        system_id: str,
        system_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._attr_unique_id = f"{system_id}_battery_energy_kwh"
        self._attr_name = "Battery Stored Energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def native_value(self) -> float | None:
        """Return stored energy in kWh."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(self._system_id, {})
        soc = system_data.get("energy_flow", {}).get("batterySoc")
        capacity = system_data.get("info", {}).get("batteryCapacity")
        if soc is None or capacity is None:
            return None
        try:
            return round(float(capacity) * float(soc) / 100, 2)
        except (ValueError, TypeError):
            return None

class SigenergyLastSyncSensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Diagnostic sensor showing last and next sync time."""

    _attr_entity_category = "diagnostic"

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        system_id: str,
        system_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._attr_unique_id = f"{system_id}_last_sync"
        self._attr_name = "Last Sync"
        self._attr_icon = "mdi:clock-sync"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            name=system_name,
            manufacturer="Sigenergy",
            model="Solar System",
        )

    @property
    def native_value(self) -> datetime.datetime | None:
        """Return the last successful update time."""
        if self.coordinator.last_update_success and self.coordinator.data:
            return self.coordinator.data.get("last_updated")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return next update time."""
        if self.coordinator.last_update_success:
            next_update = dt_util.utcnow() + self.coordinator.update_interval
            return {"next_sync": next_update.isoformat()}
        return {}


class SigenergyDeviceSensor(
    CoordinatorEntity[SigenergyCoordinator], SensorEntity
):
    """Sensor for device-level Sigenergy data."""

    entity_description: SigenergySensorDescription

    def __init__(
        self,
        coordinator: SigenergyCoordinator,
        description: SigenergySensorDescription,
        system_id: str,
        serial_number: str,
        device_type: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._system_id = system_id
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=device_name,
            manufacturer="Sigenergy",
            model=device_type,
            via_device=(DOMAIN, system_id),
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None
        system_data = self.coordinator.data.get("systems", {}).get(
            self._system_id, {}
        )
        device_data = system_data.get("devices", {}).get(
            self._serial_number, {}
        )
        realtime = device_data.get("realtime", {})
        value = realtime.get(self.entity_description.value_fn)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        return None
