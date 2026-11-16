"""Metric hierarchy.

A Metric answers one question: "what is the value at activity second N?".
Raw metrics read a timeline channel; derived metrics are *composed* from other
metrics (e.g. W/kg wraps a power metric, smoothing wraps any metric).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

from fit_render.domain import Channel, Timeline
from fit_render.units import Quantity


@dataclass(frozen=True)
class MetricContext:
    """Everything a metric may need besides the second being asked about."""

    timeline: Timeline
    rider_weight_kg: float | None = None


class Metric(ABC):
    """A named, displayable value derived from the timeline."""

    def __init__(self, key: str, label: str, quantity: Quantity, description: str = "") -> None:
        self.key = key
        self.label = label
        self.quantity = quantity
        self.description = description

    @abstractmethod
    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        """SI value at `second`, or None when unknown."""

    def required_channels(self) -> frozenset[Channel]:
        """Channels this metric reads; used to warn about missing data."""
        return frozenset()

    def chain(self) -> Iterator[Metric]:
        """This metric followed by any metrics it wraps."""
        yield self

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.key!r})"


class ChannelMetric(Metric):
    """Reads a timeline channel directly."""

    def __init__(
        self, key: str, label: str, quantity: Quantity, channel: Channel, description: str = ""
    ) -> None:
        super().__init__(key, label, quantity, description)
        self.channel = channel

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        return ctx.timeline.value(self.channel, second)

    def required_channels(self) -> frozenset[Channel]:
        return frozenset({self.channel})


class CompositeMetric(Metric):
    """A metric computed from another metric (Decorator over Metric)."""

    def __init__(
        self, key: str, label: str, quantity: Quantity, inner: Metric, description: str = ""
    ) -> None:
        super().__init__(key, label, quantity, description)
        self.inner = inner

    def required_channels(self) -> frozenset[Channel]:
        return self.inner.required_channels()

    def chain(self) -> Iterator[Metric]:
        yield self
        yield from self.inner.chain()


class SmoothedMetric(CompositeMetric):
    """Trailing rolling mean over `window_s` seconds, ignoring missing samples."""

    def __init__(self, inner: Metric, window_s: int, key: str | None = None) -> None:
        if window_s < 1:
            raise ValueError("window_s must be >= 1")
        super().__init__(
            key or f"{inner.key}_{window_s}s",
            inner.label,
            inner.quantity,
            inner,
            f"{inner.description} ({window_s}s average)".strip(),
        )
        self.window_s = window_s

    def value_at(self, ctx: MetricContext, second: int) -> float | None:
        values = [
            v
            for s in range(max(0, second - self.window_s + 1), second + 1)
            if (v := self.inner.value_at(ctx, s)) is not None
        ]
        return sum(values) / len(values) if values else None
