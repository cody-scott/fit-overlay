"""Metrics computed from other metrics or from the timeline as a whole."""

from __future__ import annotations

from datetime import UTC

from fit_render.domain import Channel
from fit_render.metrics.base import CompositeMetric, Metric, MetricContext
from fit_render.units import Quantity


class PowerToWeightMetric(CompositeMetric):
    """Power divided by rider weight (W/kg)."""

    def __init__(self, power: Metric, key: str = "power_to_weight") -> None:
        super().__init__(key, "W/kg", Quantity.POWER_TO_WEIGHT, power, "Power to weight ratio")

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        power = self.inner.value_at(ctx, second)
        if power is None or not ctx.rider_weight_kg:
            return None
        return power / ctx.rider_weight_kg


class GradientMetric(Metric):
    """Rise over run, looking back until at least `min_distance_m` has been covered."""

    def __init__(
        self, key: str = "gradient", min_distance_m: float = 20.0, max_lookback_s: int = 30
    ) -> None:
        super().__init__(key, "Grade", Quantity.GRADIENT, "Road gradient")
        self.min_distance_m = min_distance_m
        self.max_lookback_s = max_lookback_s

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        timeline = ctx.timeline
        altitude = timeline.value(Channel.ALTITUDE, second)
        distance = timeline.value(Channel.DISTANCE, second)
        if altitude is None or distance is None:
            return None
        for earlier in range(second - 1, max(-1, second - self.max_lookback_s - 1), -1):
            past_distance = timeline.value(Channel.DISTANCE, earlier)
            past_altitude = timeline.value(Channel.ALTITUDE, earlier)
            if past_distance is None or past_altitude is None:
                return None
            run = distance - past_distance
            if run >= self.min_distance_m:
                return (altitude - past_altitude) / run
        return None

    def required_channels(self) -> frozenset[Channel]:
        return frozenset({Channel.ALTITUDE, Channel.DISTANCE})


class TotalTimeMetric(Metric):
    """Wall-clock time since the activity started, including stops."""

    def __init__(self, key: str = "total_time") -> None:
        super().__init__(key, "Time", Quantity.DURATION, "Total elapsed time incl. stops")

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        return float(second)


class MovingTimeMetric(Metric):
    """Seconds spent moving since the activity started."""

    def __init__(self, key: str = "moving_time") -> None:
        super().__init__(key, "Moving", Quantity.DURATION, "Moving time (excludes stops)")

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        return float(ctx.timeline.moving_seconds_until(second))


class ClockMetric(Metric):
    """Local time of day. Uses the device's UTC offset, else this machine's zone."""

    def __init__(self, key: str = "clock") -> None:
        super().__init__(key, "Clock", Quantity.CLOCK, "Local time of day")

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        moment = ctx.timeline.timestamp_at(second)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        offset = ctx.timeline.utc_offset
        local = moment + offset if offset is not None else moment.astimezone()
        return float(local.hour * 3600 + local.minute * 60 + local.second)
