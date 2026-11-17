from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import real_fixtures

from fit_render.domain import Activity, Channel, Record, TimelineBuilder, TimerEventKind
from fit_render.errors import ActivityParseError, UnsupportedFileError
from fit_render.ingest import SpeedFromDistance, load_activity


def test_parses_synthetic_ride(activity: Activity) -> None:
    assert activity.sport == "cycling"
    assert activity.rider_weight_kg == pytest.approx(72.0)
    assert activity.utc_offset == timedelta(hours=-4)
    assert activity.duration_s == 600
    assert activity.channels_present() == set(Channel)
    assert activity.has_position
    assert activity.records[0].latitude == pytest.approx(43.45, abs=1e-6)
    kinds = [e.kind for e in activity.timer_events]
    assert kinds == [TimerEventKind.START, TimerEventKind.STOP, TimerEventKind.START,
                     TimerEventKind.STOP]  # fmt: skip


def test_records_are_sorted(activity: Activity) -> None:
    stamps = [r.timestamp for r in activity.records]
    assert stamps == sorted(stamps)


def test_missing_optional_data(make_fit) -> None:  # type: ignore[no-untyped-def]
    activity = load_activity(make_fit(weight_kg=None, utc_offset_h=None, with_power=False))
    assert activity.rider_weight_kg is None
    assert activity.utc_offset is None
    assert Channel.POWER not in activity.channels_present()


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "ride.gpx"
    path.write_text("<gpx/>")
    with pytest.raises(UnsupportedFileError):
        load_activity(path)


def test_not_a_fit_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.fit"
    path.write_bytes(b"not a fit file at all")
    with pytest.raises(ActivityParseError):
        load_activity(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ActivityParseError, match="not found"):
        load_activity(tmp_path / "nope.fit")


@pytest.mark.parametrize("path", real_fixtures(), ids=lambda p: p.name)
def test_real_fixture_files_parse(path: Path) -> None:
    activity = load_activity(path)
    assert activity.duration_s > 0
    assert activity.records


# ---- speed vs distance correction -----------------------------------------


def test_consistent_speed_is_left_alone(activity: Activity) -> None:
    assert activity.notes == ()
    assert all(r.values[Channel.SPEED] == 8.0 for r in activity.records)


def test_inconsistent_speed_is_rederived_from_distance(make_fit) -> None:  # type: ignore[no-untyped-def]
    activity = load_activity(make_fit(speed_scale=1 / 3.6))
    assert len(activity.notes) == 1
    assert "3.60x" in activity.notes[0]
    speeds = [r.values[Channel.SPEED] for r in activity.records[5:195]]
    assert speeds == pytest.approx([8.0] * len(speeds))


def test_correction_can_be_disabled(make_fit) -> None:  # type: ignore[no-untyped-def]
    activity = load_activity(make_fit(speed_scale=1 / 3.6), corrections=())
    assert activity.notes == ()
    assert activity.records[10].values[Channel.SPEED] == pytest.approx(
        8.0 / 3.6, abs=1e-3
    )  # FIT stores mm/s


def test_too_few_samples_to_judge() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    records = tuple(
        Record(start + timedelta(seconds=s), {Channel.SPEED: 1.0, Channel.DISTANCE: 8.0 * s})
        for s in range(10)
    )
    activity = Activity(records=records)
    assert SpeedFromDistance(min_samples=60).apply(activity) is activity


def test_rederived_speed_is_zero_when_distance_holds() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    distance = [0, 8, 16, 24, 32, 32, 32, 32, 32, 40, 48]
    records = tuple(
        Record(start + timedelta(seconds=s), {Channel.SPEED: 1.0, Channel.DISTANCE: float(d)})
        for s, d in enumerate(distance)
    )
    fixed = SpeedFromDistance(min_samples=1, window_s=1).apply(Activity(records=records))
    assert fixed.records[6].values[Channel.SPEED] == 0.0
    assert fixed.records[2].values[Channel.SPEED] == pytest.approx(8.0)


def test_real_trainerroad_speed_matches_distance() -> None:
    """sample_ride_1 (TrainerRoad) records speed 3.6x too small. At 6:42 the rider
    climbs at ~8.3 km/h by distance; the file says 2.3 km/h."""
    path = Path(__file__).parent / "fixtures" / "sample_ride_1.fit"
    if not path.exists():
        pytest.skip("real fixture not present")
    activity = load_activity(path)
    assert activity.notes
    timeline = TimelineBuilder().build(activity)
    window = [timeline.value(Channel.SPEED, s) for s in range(24120, 24180)]
    assert statistics.mean(v for v in window if v is not None) * 3.6 == pytest.approx(8.3, abs=0.3)
