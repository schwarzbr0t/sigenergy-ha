"""Backfill Home Assistant long-term statistics from the Sigenergy history.

The history endpoint is rate-limited to one request per station every five
minutes, so a backfill is a queue of months that the coordinator works
through in its regular polls (see SigenergyCoordinator._async_update_data).
Each request uses the Month level, which returns one value per day, so a
whole month of daily totals costs a single API call.

The values are imported into the statistics of the existing "Total" energy
sensors (and Lifetime PV Generation). That way the Energy Dashboard shows
the backfilled days without switching to a different statistic. To keep the
running `sum` consistent with the statistics Home Assistant compiled itself,
only days before a sensor's first recorded statistic are imported, and all
later rows are shifted by the imported energy with async_adjust_statistics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from functools import partial
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import SigenergyApi
from .const import DOMAIN, HISTORY_LEVEL_MONTH

_LOGGER = logging.getLogger(__name__)

# (sensor unique_id suffix, history API field) for every backfilled sensor.
# The unique_id is f"{system_id}_{suffix}", see SigenergySystemSensor.
BACKFILL_METRICS: tuple[tuple[str, str], ...] = (
    ("history_grid_import_lifetime", "powerFromGrid"),
    ("history_grid_export_lifetime", "powerToGrid"),
    ("history_battery_charging_lifetime", "esCharging"),
    ("history_battery_discharging_lifetime", "esDischarging"),
    ("history_home_consumption_lifetime", "powerUse"),
    ("summary_lifetime_generation", "powerGeneration"),
)

# A month is skipped after this many failed requests in a row
MAX_MONTH_ATTEMPTS = 3

_EPOCH = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y%m%d %H:%M",
    "%Y%m%d",
)


@dataclass
class BackfillTarget:
    """One sensor whose statistics are backfilled."""

    statistic_id: str
    field: str
    metadata: Any  # StatisticMetaData of the existing statistic
    first_day: datetime.date
    last_day: datetime.date
    base_sum: float  # sum of the last statistic row before first_day
    factor: float  # kWh -> unit of the statistic
    imported_days: int = 0


@dataclass
class BackfillJob:
    """Pending backfill for one system, worked off one month per step."""

    system_id: str
    targets: list[BackfillTarget]
    # First day of each month still to fetch, newest first. Importing the
    # newest month first leaves the statistics consistent after every step,
    # so a backfill interrupted by a restart can simply be started again.
    months: list[datetime.date] = field(default_factory=list)
    attempts: int = 0

    @property
    def done(self) -> bool:
        """Return True when all months are imported."""
        return not self.months

    async def async_step(self, hass: HomeAssistant, api: SigenergyApi) -> None:
        """Fetch the next month and import it. Raises SigenergyApiError."""
        month = self.months[0]
        data = await api.get_system_history(
            self.system_id,
            HISTORY_LEVEL_MONTH,
            month.isoformat(),
            include_items=True,
        )

        days = _daily_values(data, month)
        if not days:
            _LOGGER.warning(
                "Sigenergy history for %s (system %s) has no daily values",
                month.strftime("%Y-%m"), self.system_id,
            )
        for target in self.targets:
            _import_month(hass, target, month, days)

        self.months.pop(0)
        self.attempts = 0

    def record_failure(self) -> None:
        """Count a failed request; skip the month after too many."""
        self.attempts += 1
        if self.attempts >= MAX_MONTH_ATTEMPTS:
            _LOGGER.warning(
                "Skipping %s for system %s after %d failed requests",
                self.months[0].strftime("%Y-%m"), self.system_id, self.attempts,
            )
            self.months.pop(0)
            self.attempts = 0


def _import_month(
    hass: HomeAssistant,
    target: BackfillTarget,
    month: datetime.date,
    days: dict[datetime.date, dict[str, Any]],
) -> None:
    """Import one month of daily values into a statistic."""
    month_end = _next_month(month) - datetime.timedelta(days=1)
    first = max(month, target.first_day)
    last = min(month_end, target.last_day)
    if first > last:
        return

    statistics: list[StatisticData] = []
    total = 0.0
    day = first
    while day <= last:
        value = _to_float(days.get(day, {}).get(target.field))
        if value is not None:
            total += value * target.factor
            statistics.append(
                StatisticData(
                    start=dt_util.start_of_local_day(day),
                    sum=target.base_sum + total,
                )
            )
        day += datetime.timedelta(days=1)

    if not statistics:
        return

    async_import_statistics(hass, target.metadata, statistics)
    # Rows after this month (later months imported earlier, and everything
    # Home Assistant recorded itself) continue from the imported energy.
    get_instance(hass).async_adjust_statistics(
        target.statistic_id,
        dt_util.start_of_local_day(last + datetime.timedelta(days=1)),
        total,
        target.metadata["unit_of_measurement"],
    )
    target.imported_days += len(statistics)


async def async_plan_backfill(
    hass: HomeAssistant,
    system_id: str,
    start: datetime.date,
    end: datetime.date,
) -> BackfillJob:
    """Work out which sensors and months a backfill has to cover."""
    ent_reg = er.async_get(hass)
    recorder = get_instance(hass)
    now = dt_util.utcnow()
    range_start = dt_util.start_of_local_day(start)
    targets: list[BackfillTarget] = []

    for suffix, api_field in BACKFILL_METRICS:
        entity_id = ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{system_id}_{suffix}"
        )
        if entity_id is None:
            continue

        metadata = await recorder.async_add_executor_job(
            partial(get_metadata, hass, statistic_ids={entity_id})
        )
        if entity_id not in metadata:
            _LOGGER.info(
                "%s has no statistics yet, not backfilling it", entity_id
            )
            continue
        meta = metadata[entity_id][1]
        unit = meta.get("unit_of_measurement")
        if unit not in EnergyConverter.VALID_UNITS:
            _LOGGER.warning(
                "%s has statistics in %s, not backfilling it", entity_id, unit
            )
            continue

        # Only days before the first recorded statistic are imported
        first_recorded = await recorder.async_add_executor_job(
            _first_row_start, hass, entity_id, range_start, now
        )
        last_day = end
        if first_recorded is not None:
            last_day = min(
                end,
                dt_util.as_local(first_recorded).date() - datetime.timedelta(days=1),
            )
        if last_day < start:
            _LOGGER.info(
                "%s already has statistics from %s on, nothing to backfill",
                entity_id, start,
            )
            continue

        base_sum = await recorder.async_add_executor_job(
            _last_sum_before, hass, entity_id, range_start
        )
        targets.append(
            BackfillTarget(
                statistic_id=entity_id,
                field=api_field,
                metadata=meta,
                first_day=start,
                last_day=last_day,
                base_sum=base_sum,
                factor=EnergyConverter.convert(
                    1, UnitOfEnergy.KILO_WATT_HOUR, unit
                ),
            )
        )

    months: set[datetime.date] = set()
    for target in targets:
        month = target.first_day.replace(day=1)
        while month <= target.last_day:
            months.add(month)
            month = _next_month(month)

    return BackfillJob(
        system_id=system_id,
        targets=targets,
        months=sorted(months, reverse=True),
    )


def _first_row_start(
    hass: HomeAssistant,
    statistic_id: str,
    start: datetime.datetime,
    end: datetime.datetime,
) -> datetime.datetime | None:
    """Return the start of the first hourly statistic row in [start, end)."""
    # Find the month first, then the hour, to keep the queries small
    months = statistics_during_period(
        hass, start, end, {statistic_id}, "month", None, {"sum"}
    ).get(statistic_id)
    if not months:
        return None
    month_start = max(
        start, dt_util.utc_from_timestamp(months[0]["start"]) - datetime.timedelta(days=1)
    )
    hours = statistics_during_period(
        hass,
        month_start,
        min(end, month_start + datetime.timedelta(days=33)),
        {statistic_id},
        "hour",
        None,
        {"sum"},
    ).get(statistic_id)
    if not hours:
        return dt_util.utc_from_timestamp(months[0]["start"])
    return dt_util.utc_from_timestamp(hours[0]["start"])


def _last_sum_before(
    hass: HomeAssistant, statistic_id: str, before: datetime.datetime
) -> float:
    """Return the sum of the last statistic row starting before `before`."""
    # The monthly reduction keeps the last sum of each month
    months = statistics_during_period(
        hass, _EPOCH, before, {statistic_id}, "month", None, {"sum"}
    ).get(statistic_id)
    if not months:
        return 0.0
    return _to_float(months[-1].get("sum")) or 0.0


def _daily_values(
    data: dict[str, Any], month: datetime.date
) -> dict[datetime.date, dict[str, Any]]:
    """Map the itemList of a Month-level response to calendar days."""
    days: dict[datetime.date, dict[str, Any]] = {}
    next_month = _next_month(month)
    for item in data.get("itemList") or []:
        if not isinstance(item, dict):
            continue
        day = _parse_item_date(item.get("dataTime"))
        if day is not None and month <= day < next_month:
            days[day] = item
    return days


def _parse_item_date(value: Any) -> datetime.date | None:
    """Parse the dataTime of a history item."""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return dt_util.as_local(dt_util.utc_from_timestamp(seconds)).date()
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _next_month(month: datetime.date) -> datetime.date:
    """Return the first day of the month after `month`."""
    if month.month == 12:
        return datetime.date(month.year + 1, 1, 1)
    return datetime.date(month.year, month.month + 1, 1)


def _to_float(value: Any) -> float | None:
    """Convert an API value to float, or None."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
