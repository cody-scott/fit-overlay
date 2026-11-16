"""Metric registry: look metrics up by the key used in overlay specs."""

from __future__ import annotations

from collections.abc import Iterator

from fit_render.domain import Channel
from fit_render.metrics.base import ChannelMetric, Metric, SmoothedMetric
from fit_render.metrics.derived import (
    ClockMetric,
    GradientMetric,
    MovingTimeMetric,
    PowerToWeightMetric,
    TotalTimeMetric,
)
from fit_render.units import Quantity


class MetricRegistry:
    def __init__(self) -> None:
        self._metrics: dict[str, Metric] = {}

    def register(self, metric: Metric) -> Metric:
        if metric.key in self._metrics:
            raise ValueError(f"Metric {metric.key!r} is already registered")
        self._metrics[metric.key] = metric
        return metric

    def get(self, key: str) -> Metric:
        try:
            return self._metrics[key]
        except KeyError:
            raise KeyError(
                f"Unknown metric {key!r}; available: {', '.join(sorted(self._metrics))}"
            ) from None

    def __contains__(self, key: object) -> bool:
        return key in self._metrics

    def __iter__(self) -> Iterator[Metric]:
        return iter(self._metrics.values())


def build_default_registry() -> MetricRegistry:
    registry = MetricRegistry()
    power = registry.register(
        ChannelMetric("power", "Power", Quantity.POWER, Channel.POWER, "Power")
    )
    registry.register(SmoothedMetric(power, 3, key="power_3s"))
    registry.register(PowerToWeightMetric(power))
    registry.register(
        ChannelMetric("heart_rate", "HR", Quantity.HEART_RATE, Channel.HEART_RATE, "Heart rate")
    )
    registry.register(ChannelMetric("speed", "Speed", Quantity.SPEED, Channel.SPEED, "Speed"))
    registry.register(
        ChannelMetric("cadence", "Cadence", Quantity.CADENCE, Channel.CADENCE, "Cadence")
    )
    registry.register(
        ChannelMetric("elevation", "Elev", Quantity.ELEVATION, Channel.ALTITUDE, "Elevation")
    )
    registry.register(
        ChannelMetric("distance", "Dist", Quantity.DISTANCE, Channel.DISTANCE, "Distance")
    )
    registry.register(GradientMetric())
    registry.register(TotalTimeMetric())
    registry.register(MovingTimeMetric())
    registry.register(ClockMetric())
    return registry


default_registry = build_default_registry()
