"""Generate synthetic, deterministic FIT files for tests (via the Garmin SDK encoder).

The default ride is 600 s long with:
  * a timer stop (auto-pause, no records) from 200 s to 260 s
  * a heart-rate dropout from 300 s to 312 s
  * a 5 % climb from 400 s to 500 s
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import garmin_fit_sdk as fit

MESG = fit.Profile["mesg_num"]
START = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
SPEED_MS = 8.0


@dataclass(frozen=True)
class RideShape:
    duration_s: int = 600
    stop: tuple[int, int] | None = (200, 260)
    hr_dropout: tuple[int, int] | None = (300, 312)
    climb: tuple[int, int] = (400, 500)
    weight_kg: float | None = 72.0
    utc_offset_h: float | None = -4.0
    with_power: bool = True
    with_timer_events: bool = True


def power_at(second: int) -> int:
    return 200 + round(50 * math.sin(second / 10))


def make_ride(path: Path, shape: RideShape = RideShape()) -> Path:
    encoder = fit.Encoder()
    encoder.write_mesg(
        {"mesg_num": MESG["FILE_ID"], "type": "activity", "manufacturer": "development",
         "time_created": START}
    )  # fmt: skip
    if shape.weight_kg is not None:
        encoder.write_mesg({"mesg_num": MESG["USER_PROFILE"], "weight": shape.weight_kg})

    def timer(second: int, event_type: str) -> None:
        if shape.with_timer_events:
            encoder.write_mesg(
                {"mesg_num": MESG["EVENT"], "timestamp": START + timedelta(seconds=second),
                 "event": "timer", "event_type": event_type}
            )  # fmt: skip

    timer(0, "start")
    distance = 0.0
    altitude = 100.0
    for second in range(shape.duration_s):
        stopped = shape.stop is not None and shape.stop[0] <= second < shape.stop[1]
        if shape.stop and second == shape.stop[0]:
            timer(second - 1, "stop_all")  # devices stamp stops with the last record's time
        if shape.stop and second == shape.stop[1]:
            timer(second, "start")
        if stopped:
            continue
        if second > 0:
            distance += SPEED_MS
            if shape.climb[0] < second <= shape.climb[1]:
                altitude += SPEED_MS * 0.05
        record = {
            "mesg_num": MESG["RECORD"],
            "timestamp": START + timedelta(seconds=second),
            "speed": SPEED_MS,
            "distance": distance,
            "altitude": altitude,
            "cadence": 90,
            "position_lat": int(43.45 / 180 * 2**31),
            "position_long": int(-80.49 / 180 * 2**31),
        }
        in_dropout = shape.hr_dropout and shape.hr_dropout[0] <= second < shape.hr_dropout[1]
        if not in_dropout:
            record["heart_rate"] = 120 + second // 10
        if shape.with_power:
            record["power"] = power_at(second)
        encoder.write_mesg(record)
    end = START + timedelta(seconds=shape.duration_s - 1)
    timer(shape.duration_s - 1, "stop_all")
    if shape.utc_offset_h is not None:
        local = int(end.timestamp() + shape.utc_offset_h * 3600) - fit.FIT_EPOCH_S
        encoder.write_mesg(
            {"mesg_num": MESG["ACTIVITY"], "timestamp": end, "local_timestamp": local,
             "num_sessions": 1}
        )  # fmt: skip
    encoder.write_mesg({"mesg_num": MESG["SESSION"], "timestamp": end, "sport": "cycling"})
    path.write_bytes(encoder.close())
    return path


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic_ride.fit")
    print(make_ride(target))
