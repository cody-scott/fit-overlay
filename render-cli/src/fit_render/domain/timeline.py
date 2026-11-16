"""Resample an Activity onto a uniform 1-second grid.

The overlay updates once per second, so every downstream consumer works in
integer "activity seconds": second 0 is the first record, and time runs
continuously through stops (a stop at an intersection still advances the clock).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fit_render.domain.activity import Activity, Channel, TimerEvent, TimerEventKind

# Channels that are physically zero while the rider is stopped.
_ZERO_WHEN_STOPPED = (Channel.SPEED, Channel.POWER, Channel.CADENCE)
# Channels that hold their last value while stopped (position does not change).
_HOLD_WHEN_STOPPED = (Channel.DISTANCE, Channel.ALTITUDE)


@dataclass(frozen=True)
class Timeline:
    """Per-second channel values for a whole activity."""

    start_time: datetime
    channels: Mapping[Channel, Sequence[float | None]]
    moving: Sequence[bool]
    utc_offset: timedelta | None = None
    _moving_cumulative: list[int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Prefix sum of moving seconds, so moving time at any second is O(1).
        cumulative = [0] * (len(self.moving) + 1)
        for i, is_moving in enumerate(self.moving):
            cumulative[i + 1] = cumulative[i] + int(is_moving)
        object.__setattr__(self, "_moving_cumulative", cumulative)

    @property
    def duration_s(self) -> int:
        return len(self.moving)

    def value(self, channel: Channel, second: int) -> float | None:
        series = self.channels.get(channel)
        if series is None or not 0 <= second < len(series):
            return None
        return series[second]

    def moving_seconds_until(self, second: int) -> int:
        """Moving seconds elapsed from the activity start up to and including `second`."""
        cumulative = self._moving_cumulative
        index = max(0, min(second + 1, len(cumulative) - 1))
        return cumulative[index]

    def timestamp_at(self, second: int) -> datetime:
        return self.start_time + timedelta(seconds=second)


class TimelineBuilder:
    """Builds a Timeline from an Activity.

    Args:
        max_gap_s: gaps of up to this many seconds are filled with the last known
            value (normal recording jitter). Longer gaps stay empty and render as "--".
        moving_speed_threshold_ms: below this speed the rider counts as stopped.
    """

    def __init__(self, max_gap_s: int = 2, moving_speed_threshold_ms: float = 0.5) -> None:
        self.max_gap_s = max_gap_s
        self.moving_speed_threshold_ms = moving_speed_threshold_ms

    def build(self, activity: Activity) -> Timeline:
        n = activity.duration_s
        start = activity.start_time
        raw: dict[Channel, list[float | None]] = {ch: [None] * n for ch in Channel}

        for record in activity.records:
            second = int((record.timestamp - start).total_seconds())
            if 0 <= second < n:
                for channel, value in record.values.items():
                    raw[channel][second] = value  # last sample in a second wins

        timer_running = self._timer_running(activity.timer_events, start, n)
        channels = {ch: self._fill(series) for ch, series in raw.items()}
        self._apply_stopped_values(channels, timer_running)
        moving = self._moving(channels[Channel.SPEED], timer_running)

        present = activity.channels_present()
        return Timeline(
            start_time=start,
            channels={ch: tuple(series) for ch, series in channels.items() if ch in present},
            moving=tuple(moving),
            utc_offset=activity.utc_offset,
        )

    def _fill(self, series: list[float | None]) -> list[float | None]:
        """Forward-fill gaps no longer than max_gap_s."""
        filled = list(series)
        last_value: float | None = None
        last_index = -1
        for i, value in enumerate(series):
            if value is not None:
                last_value, last_index = value, i
            elif last_value is not None and i - last_index <= self.max_gap_s:
                filled[i] = last_value
        return filled

    @staticmethod
    def _timer_running(events: Sequence[TimerEvent], start: datetime, n: int) -> list[bool]:
        """Per-second timer state. With no timer events, assume it ran throughout.

        Devices stamp a stop event with the time of the last record before the
        pause, so a STOP takes effect the second *after* its timestamp; a START
        takes effect at its timestamp.
        """
        if not events:
            return [True] * n
        one_second = timedelta(seconds=1)
        changes = sorted(
            (e.timestamp + (one_second if e.kind is TimerEventKind.STOP else timedelta()),
             e.kind is TimerEventKind.START)
            for e in events
        )  # fmt: skip
        running = [True] * n
        state = True
        index = 0
        for second in range(n):
            moment = start + timedelta(seconds=second)
            while index < len(changes) and changes[index][0] <= moment:
                state = changes[index][1]
                index += 1
            running[second] = state
        return running

    @staticmethod
    def _apply_stopped_values(
        channels: dict[Channel, list[float | None]], timer_running: Sequence[bool]
    ) -> None:
        """While the timer is stopped and the device recorded nothing, the rider is
        stationary: speed/power/cadence are 0 and distance/altitude hold."""
        last_known: dict[Channel, float | None] = dict.fromkeys(_HOLD_WHEN_STOPPED)
        for second, running in enumerate(timer_running):
            for channel in _HOLD_WHEN_STOPPED:
                series = channels[channel]
                if series[second] is not None:
                    last_known[channel] = series[second]
                elif not running:
                    series[second] = last_known[channel]
            if not running:
                for channel in _ZERO_WHEN_STOPPED:
                    if channels[channel][second] is None:
                        channels[channel][second] = 0.0

    def _moving(self, speed: Sequence[float | None], timer_running: Sequence[bool]) -> list[bool]:
        """Moving = timer running and speed at/above threshold (unknown speed counts
        as moving while the timer runs)."""
        return [
            running and (s is None or s >= self.moving_speed_threshold_ms)
            for s, running in zip(speed, timer_running, strict=True)
        ]
