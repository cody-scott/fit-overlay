from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fitgen import RideShape, make_ride

from fit_render.domain import Activity, Timeline, TimelineBuilder
from fit_render.ingest import load_activity
from fit_render.metrics import MetricContext

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def ride_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_ride(tmp_path_factory.mktemp("fit") / "ride.fit")


@pytest.fixture(scope="session")
def make_fit(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    def _make(**shape: object) -> Path:
        directory = tmp_path_factory.mktemp("fit")
        return make_ride(directory / "ride.fit", RideShape(**shape))  # type: ignore[arg-type]

    return _make


@pytest.fixture(scope="session")
def activity(ride_path: Path) -> Activity:
    return load_activity(ride_path)


@pytest.fixture(scope="session")
def timeline(activity: Activity) -> Timeline:
    return TimelineBuilder().build(activity)


@pytest.fixture(scope="session")
def ctx(timeline: Timeline, activity: Activity) -> MetricContext:
    return MetricContext(timeline=timeline, rider_weight_kg=activity.rider_weight_kg)


def real_fixtures() -> list[Path]:
    """User-supplied .fit files dropped into tests/fixtures/."""
    return sorted(FIXTURES.glob("*.fit")) if FIXTURES.is_dir() else []
