"""Turn SI metric values into display text (Strategy per quantity)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

MISSING = "--"


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class Quantity(StrEnum):
    """What a metric value measures. Values are always passed in SI units."""

    POWER = "power"  # W
    POWER_TO_WEIGHT = "power_to_weight"  # W/kg
    HEART_RATE = "heart_rate"  # bpm
    SPEED = "speed"  # m/s
    CADENCE = "cadence"  # rpm
    ELEVATION = "elevation"  # m
    DISTANCE = "distance"  # m
    GRADIENT = "gradient"  # fraction (0.05 == 5 %)
    DURATION = "duration"  # s
    CLOCK = "clock"  # seconds since local midnight


@dataclass(frozen=True, slots=True)
class FormattedValue:
    text: str
    unit: str


class QuantityFormatter(ABC):
    @abstractmethod
    def format(self, value: float | None, units: UnitSystem) -> FormattedValue: ...


@dataclass(frozen=True)
class NumberFormatter(QuantityFormatter):
    """Scales an SI value into the chosen unit system and rounds it."""

    metric_unit: str
    metric_factor: float = 1.0
    imperial_unit: str | None = None  # None: same as metric
    imperial_factor: float | None = None
    decimals: int = 0

    def format(self, value: float | None, units: UnitSystem) -> FormattedValue:
        if units is UnitSystem.IMPERIAL and self.imperial_unit is not None:
            unit, factor = self.imperial_unit, self.imperial_factor or 1.0
        else:
            unit, factor = self.metric_unit, self.metric_factor
        if value is None:
            return FormattedValue(MISSING, unit)
        scaled = value * factor
        text = f"{scaled:.{self.decimals}f}"
        if text.startswith("-") and float(text) == 0:
            text = text[1:]  # avoid "-0.0"
        return FormattedValue(text, unit)


class DurationFormatter(QuantityFormatter):
    """H:MM:SS (always shows hours, so the width is steady through a ride)."""

    def format(self, value: float | None, units: UnitSystem) -> FormattedValue:
        if value is None:
            return FormattedValue(MISSING, "")
        hours, remainder = divmod(int(value), 3600)
        minutes, seconds = divmod(remainder, 60)
        return FormattedValue(f"{hours}:{minutes:02d}:{seconds:02d}", "")


class ClockFormatter(QuantityFormatter):
    """24-hour HH:MM:SS local time of day."""

    def format(self, value: float | None, units: UnitSystem) -> FormattedValue:
        if value is None:
            return FormattedValue(MISSING, "")
        hours, remainder = divmod(int(value) % 86400, 3600)
        minutes, seconds = divmod(remainder, 60)
        return FormattedValue(f"{hours:02d}:{minutes:02d}:{seconds:02d}", "")


_MS_TO_KMH = 3.6
_MS_TO_MPH = 2.236936
_M_TO_KM = 0.001
_M_TO_MI = 1 / 1609.344
_M_TO_FT = 3.280840

_FORMATTERS: dict[Quantity, QuantityFormatter] = {
    Quantity.POWER: NumberFormatter("W"),
    Quantity.POWER_TO_WEIGHT: NumberFormatter("W/kg", decimals=1),
    Quantity.HEART_RATE: NumberFormatter("bpm"),
    Quantity.SPEED: NumberFormatter("km/h", _MS_TO_KMH, "mph", _MS_TO_MPH, decimals=1),
    Quantity.CADENCE: NumberFormatter("rpm"),
    Quantity.ELEVATION: NumberFormatter("m", 1.0, "ft", _M_TO_FT),
    Quantity.DISTANCE: NumberFormatter("km", _M_TO_KM, "mi", _M_TO_MI, decimals=2),
    Quantity.GRADIENT: NumberFormatter("%", 100.0, decimals=1),
    Quantity.DURATION: DurationFormatter(),
    Quantity.CLOCK: ClockFormatter(),
}


def formatter_for(quantity: Quantity) -> QuantityFormatter:
    return _FORMATTERS[quantity]
