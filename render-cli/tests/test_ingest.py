from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from conftest import real_fixtures

from fit_render.domain import Activity, Channel, TimerEventKind
from fit_render.errors import ActivityParseError, UnsupportedFileError
from fit_render.ingest import load_activity


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
