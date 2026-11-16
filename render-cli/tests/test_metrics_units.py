from __future__ import annotations

import pytest
from fitgen import SPEED_MS, power_at

from fit_render.metrics import (
    MetricContext,
    SmoothedMetric,
    build_default_registry,
    default_registry,
)
from fit_render.units import MISSING, Quantity, UnitSystem, formatter_for

M = UnitSystem.METRIC
I = UnitSystem.IMPERIAL  # noqa: E741


def value(key: str, ctx: MetricContext, second: int) -> float | None:
    return default_registry.get(key).value_at(ctx, second)


def test_raw_channels(ctx: MetricContext) -> None:
    assert value("power", ctx, 50) == power_at(50)
    assert value("speed", ctx, 50) == pytest.approx(SPEED_MS)
    assert value("heart_rate", ctx, 50) == 125


def test_power_3s_is_trailing_mean(ctx: MetricContext) -> None:
    expected = sum(power_at(s) for s in (48, 49, 50)) / 3
    assert value("power_3s", ctx, 50) == pytest.approx(expected)
    assert value("power_3s", ctx, 0) == power_at(0)  # window clipped at start


def test_smoothing_ignores_missing_samples(ctx: MetricContext) -> None:
    hr = default_registry.get("heart_rate")
    smoothed = SmoothedMetric(hr, 5)
    assert smoothed.value_at(ctx, 307) is None  # whole window inside the dropout
    assert smoothed.key == "heart_rate_5s"


def test_power_to_weight(ctx: MetricContext) -> None:
    assert value("power_to_weight", ctx, 50) == pytest.approx(power_at(50) / 72.0)
    no_weight = MetricContext(timeline=ctx.timeline, rider_weight_kg=None)
    assert value("power_to_weight", no_weight, 50) is None


def test_gradient(ctx: MetricContext) -> None:
    assert value("gradient", ctx, 100) == pytest.approx(0.0, abs=1e-3)
    assert value("gradient", ctx, 450) == pytest.approx(0.05, abs=0.005)
    assert value("gradient", ctx, 230) is None  # stopped: no distance covered


def test_stop_behaviour(ctx: MetricContext) -> None:
    assert value("speed", ctx, 230) == 0.0
    assert value("power", ctx, 230) == 0.0
    assert value("heart_rate", ctx, 230) is None  # no data while paused -> "--"
    assert value("heart_rate", ctx, 301) == 149  # short gap filled from 299
    assert value("heart_rate", ctx, 305) is None  # long dropout


def test_times(ctx: MetricContext) -> None:
    assert value("total_time", ctx, 300) == 300
    assert value("moving_time", ctx, 300) == 301 - 60  # 60 s stop excluded
    assert value("clock", ctx, 0) == 8 * 3600  # 12:00 UTC at UTC-4


def test_registry_rejects_duplicates_and_unknown() -> None:
    registry = build_default_registry()
    with pytest.raises(ValueError, match="already"):
        registry.register(registry.get("power"))
    with pytest.raises(KeyError, match="Unknown metric"):
        registry.get("watts")


@pytest.mark.parametrize(
    ("quantity", "si", "units", "text", "unit"),
    [
        (Quantity.POWER, 247.6, M, "248", "W"),
        (Quantity.SPEED, 10.0, M, "36.0", "km/h"),
        (Quantity.SPEED, 10.0, I, "22.4", "mph"),
        (Quantity.DISTANCE, 12345.0, M, "12.35", "km"),
        (Quantity.DISTANCE, 1609.344, I, "1.00", "mi"),
        (Quantity.ELEVATION, 100.0, I, "328", "ft"),
        (Quantity.GRADIENT, 0.054, M, "5.4", "%"),
        (Quantity.GRADIENT, -0.0001, M, "0.0", "%"),
        (Quantity.POWER_TO_WEIGHT, 3.456, M, "3.5", "W/kg"),
        (Quantity.DURATION, 3725.0, M, "1:02:05", ""),
        (Quantity.CLOCK, 8 * 3600 + 5, M, "08:00:05", ""),
        (Quantity.HEART_RATE, None, M, MISSING, "bpm"),
        (Quantity.DURATION, None, M, MISSING, ""),
    ],
)
def test_formatting(
    quantity: Quantity, si: float | None, units: UnitSystem, text: str, unit: str
) -> None:
    formatted = formatter_for(quantity).format(si, units)
    assert (formatted.text, formatted.unit) == (text, unit)
