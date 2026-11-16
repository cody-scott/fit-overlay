"""FIT file parser backed by Garmin's official SDK (garmin-fit-sdk)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, cast

import garmin_fit_sdk as fit

from fit_render.domain import Activity, Channel, Record, TimerEvent, TimerEventKind
from fit_render.errors import ActivityParseError
from fit_render.ingest.base import ActivityParser

_SEMICIRCLE_TO_DEG = 180.0 / 2**31

# FIT record field -> channel. Earlier entries win (enhanced_* are higher resolution).
_FIELD_MAP: tuple[tuple[str, Channel], ...] = (
    ("power", Channel.POWER),
    ("heart_rate", Channel.HEART_RATE),
    ("enhanced_speed", Channel.SPEED),
    ("speed", Channel.SPEED),
    ("cadence", Channel.CADENCE),
    ("enhanced_altitude", Channel.ALTITUDE),
    ("altitude", Channel.ALTITUDE),
    ("distance", Channel.DISTANCE),
)

_STOP_EVENT_TYPES = {"stop", "stop_all", "stop_disable", "stop_disable_all"}


class FitParser(ActivityParser):
    extensions: ClassVar[tuple[str, ...]] = (".fit",)

    def _parse(self, path: Path) -> Activity:
        messages = self._decode(path)
        records = sorted(
            (r for r in map(self._record, messages.get("record_mesgs", [])) if r is not None),
            key=lambda r: r.timestamp,
        )
        return Activity(
            records=tuple(records),
            timer_events=tuple(self._timer_events(messages.get("event_mesgs", []))),
            rider_weight_kg=self._weight(messages.get("user_profile_mesgs", [])),
            utc_offset=self._utc_offset(messages.get("activity_mesgs", [])),
            sport=self._sport(messages),
        )

    @staticmethod
    def _decode(path: Path) -> dict[str, list[dict[str, Any]]]:
        try:
            stream = fit.Stream.from_file(str(path))
            decoder = fit.Decoder(stream)
            if not decoder.is_fit():
                raise ActivityParseError(f"{path.name} is not a FIT file.")
            messages, errors = decoder.read()
        except ActivityParseError:
            raise
        except Exception as exc:  # the SDK raises a variety of low-level errors
            raise ActivityParseError(f"Could not decode {path.name}: {exc}") from exc
        if errors and not messages.get("record_mesgs"):
            raise ActivityParseError(f"Could not decode {path.name}: {errors[0]}")
        # Truncated files (e.g. device crash) still decode up to the damage; keep them.
        return cast(dict[str, list[dict[str, Any]]], messages)

    @staticmethod
    def _record(mesg: dict[str, Any]) -> Record | None:
        timestamp = mesg.get("timestamp")
        if not isinstance(timestamp, datetime):
            return None
        values: dict[Channel, float] = {}
        for field_name, channel in _FIELD_MAP:
            value = mesg.get(field_name)
            if channel not in values and isinstance(value, int | float):
                values[channel] = float(value)
        lat, lon = mesg.get("position_lat"), mesg.get("position_long")
        return Record(
            timestamp=timestamp,
            values=values,
            latitude=lat * _SEMICIRCLE_TO_DEG if isinstance(lat, int) else None,
            longitude=lon * _SEMICIRCLE_TO_DEG if isinstance(lon, int) else None,
        )

    @staticmethod
    def _timer_events(mesgs: list[dict[str, Any]]) -> list[TimerEvent]:
        events: list[TimerEvent] = []
        for mesg in mesgs:
            timestamp = mesg.get("timestamp")
            if mesg.get("event") != "timer" or not isinstance(timestamp, datetime):
                continue
            event_type = mesg.get("event_type")
            if event_type == "start":
                events.append(TimerEvent(timestamp, TimerEventKind.START))
            elif event_type in _STOP_EVENT_TYPES:
                events.append(TimerEvent(timestamp, TimerEventKind.STOP))
        return sorted(events, key=lambda e: e.timestamp)

    @staticmethod
    def _weight(mesgs: list[dict[str, Any]]) -> float | None:
        for mesg in mesgs:
            weight = mesg.get("weight")
            if isinstance(weight, int | float) and weight > 0:
                return float(weight)
        return None

    @staticmethod
    def _utc_offset(mesgs: list[dict[str, Any]]) -> timedelta | None:
        """activity.local_timestamp is device-local FIT seconds; diff against UTC."""
        for mesg in mesgs:
            timestamp, local = mesg.get("timestamp"), mesg.get("local_timestamp")
            if isinstance(timestamp, datetime) and isinstance(local, int):
                offset_s = (local + fit.FIT_EPOCH_S) - timestamp.timestamp()
                quarter_hours = round(offset_s / 900)  # real offsets are 15-min multiples
                return timedelta(minutes=15 * quarter_hours)
        return None

    @staticmethod
    def _sport(messages: dict[str, list[dict[str, Any]]]) -> str | None:
        for key in ("session_mesgs", "sport_mesgs"):
            for mesg in messages.get(key, []):
                sport = mesg.get("sport")
                if isinstance(sport, str):
                    return sport
        return None
