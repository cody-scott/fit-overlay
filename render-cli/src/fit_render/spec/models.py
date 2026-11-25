"""Overlay spec schema (v1).

A spec is pure data: it says *what* to draw and *where*, never how. The render
unit turns it into widget objects. Positions and sizes are fractions of the
frame, so one spec works at any resolution or aspect ratio.
"""

from __future__ import annotations

import re
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, field_validator

from fit_render.units import UnitSystem

FRAME_SIZES: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2.7k": (2704, 1520),
    "4k": (3840, 2160),
    "vertical-720": (720, 1280),
    "vertical-1080": (1080, 1920),
    "vertical-4k": (2160, 3840),
    "square-1080": (1080, 1080),
}

FRAME_RATES: dict[str, Fraction] = {
    "23.976": Fraction(24000, 1001),
    "24": Fraction(24),
    "25": Fraction(25),
    "29.97": Fraction(30000, 1001),
    "30": Fraction(30),
    "50": Fraction(50),
    "59.94": Fraction(60000, 1001),
    "60": Fraction(60),
}

_CUSTOM_SIZE_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")
_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class OutputFormat(StrEnum):
    PRORES_4444 = "prores4444"  # .mov  - Premiere, Final Cut, Resolve
    WEBM = "webm"  # .webm - small files; limited editor support
    PNG_SEQUENCE = "png-seq"  # directory of PNGs - universal fallback


class Anchor(StrEnum):
    TOP_LEFT = "top-left"
    TOP = "top"
    TOP_RIGHT = "top-right"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM = "bottom"
    BOTTOM_RIGHT = "bottom-right"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def parse_frame_size(value: str) -> tuple[int, int]:
    if value in FRAME_SIZES:
        return FRAME_SIZES[value]
    match = _CUSTOM_SIZE_RE.match(value)
    if not match:
        raise ValueError(
            f"Unknown size {value!r}; use one of {', '.join(FRAME_SIZES)} or WIDTHxHEIGHT"
        )
    width, height = int(match[1]), int(match[2])
    if width % 2 or height % 2:
        raise ValueError(f"Size {value!r} must have even width and height")
    return width, height


class OutputSpec(_Model):
    size: str = Field("1080p", description="Frame size preset or WIDTHxHEIGHT.")
    fps: str = Field("30", description="Frame rate.")
    format: OutputFormat = Field(
        OutputFormat.PRORES_4444,
        description="prores4444 (.mov, every editor), webm (small, limited support), png-seq.",
    )

    @field_validator("size")
    @classmethod
    def _check_size(cls, value: str) -> str:
        parse_frame_size(value)
        return value

    @field_validator("fps", mode="before")
    @classmethod
    def _check_fps(cls, value: object) -> str:
        text = str(value)
        if text not in FRAME_RATES:
            raise ValueError(f"Unsupported fps {text!r}; use one of {', '.join(FRAME_RATES)}")
        return text

    @property
    def resolution(self) -> tuple[int, int]:
        return parse_frame_size(self.size)

    @property
    def frame_rate(self) -> Fraction:
        return FRAME_RATES[self.fps]


class TextStyle(_Model):
    font: str = "roboto-mono-bold"
    color: str = "#FFFFFF"

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str) -> str:
        if not _COLOR_RE.match(value):
            raise ValueError(f"Color {value!r} must be #RGB, #RRGGBB or #RRGGBBAA")
        return value


class _WidgetSpec(_Model):
    anchor: Anchor = Field(
        Anchor.TOP_LEFT, description="Frame point the widget is pinned to; also aligns the text."
    )
    offset: tuple[float, float] = Field(
        (0.03, 0.03), description="Inset from the anchor edge(s), as fractions of width/height."
    )
    size: float = Field(
        0.05, gt=0.0, le=0.5, description="Font size (em) as a fraction of frame height."
    )
    font: str | None = None  # overrides the spec-level style
    color: str | None = None

    @field_validator("offset")
    @classmethod
    def _check_offset(cls, value: tuple[float, float]) -> tuple[float, float]:
        if not all(0.0 <= v <= 1.0 for v in value):
            raise ValueError("offset values must be between 0 and 1")
        return value

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        return None if value is None else TextStyle._check_color(value)


class MetricWidgetSpec(_WidgetSpec):
    type: Literal["metric"] = "metric"
    metric: str
    label: str | None = Field(None, description="Text before the value, e.g. 'HR'.")
    show_unit: bool = Field(True, description="Append the unit, e.g. 'W' or 'km/h'.")
    smoothing_s: int | None = Field(
        None, ge=1, le=60, description="Trailing rolling average window in seconds."
    )


class LabelWidgetSpec(_WidgetSpec):
    type: Literal["label"] = "label"
    text: str = Field(min_length=1, description="Static text to draw.")


def _widget_type(value: object) -> str:
    """Discriminator that defaults to 'metric' when `type` is omitted."""
    if isinstance(value, dict):
        return str(value.get("type", "metric"))
    return str(getattr(value, "type", "metric"))


WidgetSpec = Annotated[
    Annotated[MetricWidgetSpec, Tag("metric")] | Annotated[LabelWidgetSpec, Tag("label")],
    Discriminator(_widget_type),
]


class RiderSpec(_Model):
    weight_kg: float | None = Field(
        None, gt=20, lt=300, description="For power_to_weight; falls back to the FIT profile."
    )


class OverlaySpec(_Model):
    version: Literal[1] = 1
    name: str = Field("custom", description="Short identifier; templates use the file name.")
    description: str = Field("", description="One line shown by `templates list`.")
    units: UnitSystem = Field(
        UnitSystem.METRIC, description="imperial switches speed, distance and elevation."
    )
    rider: RiderSpec = RiderSpec()
    output: OutputSpec = OutputSpec()
    style: TextStyle = TextStyle()
    widgets: list[WidgetSpec] = Field(min_length=1, description="Drawn in order.")
