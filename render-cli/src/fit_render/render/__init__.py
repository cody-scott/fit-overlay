"""Render unit: turn a spec into widgets and draw frames."""

from fit_render.render.builder import OverlayBuilder, parse_color
from fit_render.render.canvas import RGBA, Canvas, PillowCanvas
from fit_render.render.fonts import FontLibrary
from fit_render.render.layout import Placement
from fit_render.render.widgets import (
    FrameState,
    LabelWidget,
    MetricWidget,
    Overlay,
    TextStyle,
    TextWidget,
    Widget,
)

__all__ = [
    "RGBA",
    "Canvas",
    "FontLibrary",
    "FrameState",
    "LabelWidget",
    "MetricWidget",
    "Overlay",
    "OverlayBuilder",
    "PillowCanvas",
    "Placement",
    "TextStyle",
    "TextWidget",
    "Widget",
    "parse_color",
]
