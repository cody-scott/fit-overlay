from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fit_render.domain import (
    Activity,
    Channel,
    Record,
    Slice,
    Timeline,
    TimelineBuilder,
    TimerEvent,
    TimerEventKind,
    parse_time,
)
from fit_render.errors import SliceError

T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("45", 45), ("90", 90), ("1:30", 90), ("0:12:30", 750), ("1:00:00", 3600), (" 2:05 ", 125)],
)
def test_parse_time(text: str, seconds: int) -> None:
    assert parse_time(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "1:2:3:4", "1:75", "1:61:00", "-5"])
def test_parse_time_rejects(text: str) -> None:
    with pytest.raises(SliceError):
        parse_time(text)


def test_slice_validation() -> None:
    assert Slice(0, 30).validate(600) == []
    assert Slice(0, 31).validate(600)  # warning
    with pytest.raises(SliceError, match="maximum"):
        Slice(0, 181).validate(600)
    with pytest.raises(SliceError, match="after start"):
        Slice(10, 10).validate(600)
    with pytest.raises(SliceError, match="only"):
        Slice(590, 610).validate(600)


def _activity(values: dict[int, dict[Channel, float]], events: list[TimerEvent] = ()) -> Activity:  # type: ignore[assignment]
    records = tuple(Record(T0 + timedelta(seconds=s), v) for s, v in sorted(values.items()))
    return Activity(records=records, timer_events=tuple(events))


def test_gap_fill_respects_max_gap() -> None:
    hr = Channel.HEART_RATE
    activity = _activity({0: {hr: 100}, 1: {hr: 101}, 10: {hr: 110}})
    timeline = TimelineBuilder(max_gap_s=2).build(activity)
    assert [timeline.value(hr, s) for s in range(5)] == [100, 101, 101, 101, None]
    assert timeline.value(hr, 10) == 110


def test_stopped_timer_zeroes_motion_and_holds_position() -> None:
    sp, dist = Channel.SPEED, Channel.DISTANCE
    activity = _activity(
        {0: {sp: 8, dist: 0}, 1: {sp: 8, dist: 8}, 9: {sp: 8, dist: 16}},
        [TimerEvent(T0 + timedelta(seconds=1), TimerEventKind.STOP),
         TimerEvent(T0 + timedelta(seconds=9), TimerEventKind.START)],
    )  # fmt: skip
    timeline = TimelineBuilder(max_gap_s=0).build(activity)
    assert not timeline.moving[2]  # stop stamped at 1 takes effect from second 2
    assert timeline.value(sp, 5) == 0.0
    assert timeline.value(dist, 5) == 8
    assert timeline.moving_seconds_until(9) == 3  # seconds 0, 1, 9
    assert timeline.duration_s == 10


def test_slow_speed_counts_as_stopped_without_timer_events() -> None:
    sp = Channel.SPEED
    activity = _activity({0: {sp: 5}, 1: {sp: 0.1}, 2: {sp: 0.0}, 3: {sp: 5}})
    timeline = TimelineBuilder().build(activity)
    assert list(timeline.moving) == [True, False, False, True]


def test_timeline_only_exposes_recorded_channels(timeline: Timeline) -> None:
    assert Channel.POWER in timeline.channels
    assert timeline.value(Channel.POWER, -1) is None
    assert timeline.value(Channel.POWER, 10_000) is None
