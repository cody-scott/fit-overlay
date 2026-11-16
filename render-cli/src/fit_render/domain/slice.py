"""The [start, end) window of activity time to render."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fit_render.errors import SliceError

_TIME_RE = re.compile(r"^(?:(?:(\d+):)?(\d{1,2}):)?(\d+)$")


def parse_time(text: str) -> int:
    """Parse 'H:MM:SS', 'MM:SS' or 'SS' (time since activity start) into seconds."""
    match = _TIME_RE.match(text.strip())
    if not match:
        raise SliceError(f"Invalid time {text!r}; expected H:MM:SS, MM:SS or seconds.")
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    if (hours or minutes) and seconds >= 60:
        raise SliceError(f"Invalid time {text!r}: seconds must be < 60.")
    if hours and minutes >= 60:
        raise SliceError(f"Invalid time {text!r}: minutes must be < 60.")
    return hours * 3600 + minutes * 60 + seconds


def format_time(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True, slots=True)
class Slice:
    """A window of whole activity seconds: start inclusive, end exclusive."""

    start_s: int
    end_s: int

    WARN_DURATION_S = 30
    MAX_DURATION_S = 180

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s

    @classmethod
    def parse(cls, start: str, end: str) -> Slice:
        return cls(parse_time(start), parse_time(end))

    def validate(self, activity_duration_s: int) -> list[str]:
        """Raise SliceError for invalid slices; return warnings for unusual ones."""
        if self.end_s <= self.start_s:
            raise SliceError("End must be after start.")
        if self.end_s > activity_duration_s:
            raise SliceError(
                f"Slice ends at {format_time(self.end_s)} but the activity is only "
                f"{format_time(activity_duration_s)} long."
            )
        if self.duration_s > self.MAX_DURATION_S:
            raise SliceError(f"Slice is {self.duration_s}s; the maximum is {self.MAX_DURATION_S}s.")
        if self.duration_s > self.WARN_DURATION_S:
            return [
                f"Slice is {self.duration_s}s (over {self.WARN_DURATION_S}s); "
                "rendering will take longer and files will be large."
            ]
        return []
