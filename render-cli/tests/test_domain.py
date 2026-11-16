from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from fit_render.ingest import load_activity

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


def test_long_recording_gap_without_timer_events_is_a_pause() -> None:
    sp, dist, hr = Channel.SPEED, Channel.DISTANCE, Channel.HEART_RATE
    activity = _activity(
        {0: {sp: 8, dist: 0, hr: 120}, 1: {sp: 8, dist: 8, hr: 121},
         30: {sp: 8, dist: 16, hr: 110}, 31: {sp: 8, dist: 24, hr: 111}},
    )  # fmt: skip
    timeline = TimelineBuilder(max_gap_s=0, pause_gap_s=10).build(activity)
    assert not any(timeline.moving[2:30])
    assert timeline.value(sp, 15) == 0.0
    assert timeline.value(dist, 15) == 8
    assert timeline.value(hr, 15) is None
    assert timeline.moving_seconds_until(31) == 4  # seconds 0, 1, 30, 31


def test_short_recording_gap_is_not_a_pause() -> None:
    """Smart recording logs every few seconds while riding; that is not a stop."""
    sp = Channel.SPEED
    activity = _activity({0: {sp: 8}, 6: {sp: 8}, 12: {sp: 8}})
    timeline = TimelineBuilder(max_gap_s=2, pause_gap_s=10).build(activity)
    assert all(timeline.moving)
    assert timeline.value(sp, 4) is None  # beyond forward-fill, not zeroed


def test_real_ride_recording_gap_is_a_pause() -> None:
    """sample_ride_1 (TrainerRoad) has no pause events; records stop for 534 s
    after 1:02:03. That must read as stopped, not as 9 minutes of '--' riding."""
    path = Path(__file__).parent / "fixtures" / "sample_ride_1.fit"
    if not path.exists():
        pytest.skip("real fixture not present")
    timeline = TimelineBuilder().build(load_activity(path))
    inside = 3900  # 1:05:00
    assert timeline.value(Channel.SPEED, inside) == 0.0
    assert timeline.value(Channel.DISTANCE, inside) == pytest.approx(20471.6)
    assert timeline.value(Channel.HEART_RATE, inside) is None
    assert timeline.moving_seconds_until(4257) == timeline.moving_seconds_until(3724)
