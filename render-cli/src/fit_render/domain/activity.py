"""Parser-agnostic activity model.

Parsers (FIT today, GPX/TCX later) translate their source format into these
types. Nothing downstream of ingest knows which file format was used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class Channel(StrEnum):
    """A raw, per-sample data channel recorded by the device (SI units)."""

    POWER = "power"  # W
    HEART_RATE = "heart_rate"  # bpm
    SPEED = "speed"  # m/s
    CADENCE = "cadence"  # rpm
    ALTITUDE = "altitude"  # m
    DISTANCE = "distance"  # m (cumulative)


@dataclass(frozen=True, slots=True)
class Record:
    """One sample from the device. Missing values are None."""

    timestamp: datetime
    values: dict[Channel, float] = field(default_factory=dict)
    latitude: float | None = None
    longitude: float | None = None


class TimerEventKind(StrEnum):
    START = "start"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class TimerEvent:
    """The device timer starting or stopping (manual or auto-pause)."""

    timestamp: datetime
    kind: TimerEventKind


@dataclass(frozen=True, slots=True)
class Activity:
    """A parsed activity. Records are sorted by timestamp."""

    records: tuple[Record, ...]
    timer_events: tuple[TimerEvent, ...] = ()
    rider_weight_kg: float | None = None
    utc_offset: timedelta | None = None  # device local time minus UTC, if known
    sport: str | None = None
    # Data-quality notes from ingest corrections, shown to the user as warnings.
    notes: tuple[str, ...] = ()

    @property
    def start_time(self) -> datetime:
        return self.records[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.records[-1].timestamp

    @property
    def duration_s(self) -> int:
        """Wall-clock duration in whole seconds, including stops."""
        return int((self.end_time - self.start_time).total_seconds()) + 1

    def channels_present(self) -> set[Channel]:
        present: set[Channel] = set()
        for record in self.records:
            present.update(record.values)
        return present

    @property
    def has_position(self) -> bool:
        return any(r.latitude is not None for r in self.records)
