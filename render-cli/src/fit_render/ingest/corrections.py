"""Post-parse corrections for known device/app data defects (Strategy).

Each correction inspects a parsed Activity and returns it unchanged or with the
defect repaired plus a note explaining what was done. They are format-agnostic:
they look at the data, not at which app wrote the file.
"""

from __future__ import annotations

import dataclasses
import statistics
from abc import ABC, abstractmethod
from collections.abc import Sequence
from itertools import pairwise

from fit_render.domain import Activity, Channel, Record


class ActivityCorrection(ABC):
    @abstractmethod
    def apply(self, activity: Activity) -> Activity:
        """Return the activity, corrected if this defect is present."""


class SpeedFromDistance(ActivityCorrection):
    """Replace recorded speed with distance-derived speed when the two disagree.

    Some apps write a per-record speed that is inconsistent with the cumulative
    distance in the same file (TrainerRoad exports speed 3.6x too small, i.e. a
    m/s <-> km/h mix-up) while distance and the session totals are correct. When
    the median ratio of distance change to recorded speed, over moving samples,
    is outside `tolerance`, speed is recomputed from distance over a centred
    window of +/- `window_s` seconds (distance is often quantised to ~0.5 m, so a
    single-second difference jitters).

    Args:
        tolerance: (low, high) accepted range for the median ratio.
        min_samples: fewer usable samples than this -> leave the data alone.
        window_s: half-width of the window used to differentiate distance.
        min_speed_ms: samples slower than this are ignored for detection.
        max_dt_s: record pairs further apart than this are ignored for detection.
    """

    def __init__(
        self,
        tolerance: tuple[float, float] = (0.8, 1.25),
        min_samples: int = 60,
        window_s: int = 2,
        min_speed_ms: float = 0.5,
        max_dt_s: float = 5.0,
    ) -> None:
        self.tolerance = tolerance
        self.min_samples = min_samples
        self.window_s = window_s
        self.min_speed_ms = min_speed_ms
        self.max_dt_s = max_dt_s

    def apply(self, activity: Activity) -> Activity:
        ratio = self.distance_to_speed_ratio(activity.records)
        if ratio is None or self.tolerance[0] <= ratio <= self.tolerance[1]:
            return activity
        note = (
            f"Recorded speed disagrees with distance (distance implies {ratio:.2f}x the "
            "recorded speed); using speed derived from distance."
        )
        return dataclasses.replace(
            activity,
            records=self._rederive(activity.records),
            notes=(*activity.notes, note),
        )

    def distance_to_speed_ratio(self, records: Sequence[Record]) -> float | None:
        """Median of (distance change / time) / recorded speed over moving samples."""
        ratios: list[float] = []
        usable = [r for r in records if {Channel.DISTANCE, Channel.SPEED} <= r.values.keys()]
        for a, b in pairwise(usable):
            dt = (b.timestamp - a.timestamp).total_seconds()
            speed = (a.values[Channel.SPEED] + b.values[Channel.SPEED]) / 2
            if 0 < dt <= self.max_dt_s and speed >= self.min_speed_ms:
                moved = b.values[Channel.DISTANCE] - a.values[Channel.DISTANCE]
                ratios.append(moved / dt / speed)
        if len(ratios) < self.min_samples:
            return None
        return statistics.median(ratios)

    def _rederive(self, records: Sequence[Record]) -> tuple[Record, ...]:
        """New records whose speed is the distance slope over a centred window.

        Records without distance (or without a neighbour in the window) lose their
        speed: the recorded value is known to be wrong, so showing "--" is better.
        """
        with_distance = [
            (r.timestamp, d) for r in records if (d := r.values.get(Channel.DISTANCE)) is not None
        ]
        out: list[Record] = []
        lo = hi = 0
        for record in records:
            values: dict[Channel, float] = {
                ch: v for ch, v in record.values.items() if ch is not Channel.SPEED
            }
            if Channel.DISTANCE in record.values:
                t = record.timestamp
                while (t - with_distance[lo][0]).total_seconds() > self.window_s:
                    lo += 1
                while (
                    hi + 1 < len(with_distance)
                    and (with_distance[hi + 1][0] - t).total_seconds() <= self.window_s
                ):
                    hi += 1
                (t0, d0), (t1, d1) = with_distance[lo], with_distance[hi]
                span = (t1 - t0).total_seconds()
                if span > 0:
                    values[Channel.SPEED] = max(0.0, (d1 - d0) / span)
            out.append(dataclasses.replace(record, values=values))
        return tuple(out)


DEFAULT_CORRECTIONS: tuple[ActivityCorrection, ...] = (SpeedFromDistance(),)


def apply_corrections(
    activity: Activity, corrections: Sequence[ActivityCorrection] = DEFAULT_CORRECTIONS
) -> Activity:
    for correction in corrections:
        activity = correction.apply(activity)
    return activity
