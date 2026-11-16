"""Domain unit: format-agnostic activity model and the per-second timeline."""

from fit_render.domain.activity import Activity, Channel, Record, TimerEvent, TimerEventKind
from fit_render.domain.slice import Slice, parse_time
from fit_render.domain.timeline import Timeline, TimelineBuilder

__all__ = [
    "Activity",
    "Channel",
    "Record",
    "Slice",
    "Timeline",
    "TimelineBuilder",
    "TimerEvent",
    "TimerEventKind",
    "parse_time",
]
