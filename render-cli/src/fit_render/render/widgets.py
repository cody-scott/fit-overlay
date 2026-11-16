"""Widget hierarchy and the Overlay composite.

Rendering is split in two steps so frames can be de-duplicated:
  1. content(frame) -> str: the widget's visible state at a moment (cheap)
  2. draw(canvas, content): paint that state (expensive)
If every widget's content matches the previous frame, the frame is reused.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from fit_render.domain import Channel
from fit_render.metrics import Metric, MetricContext
from fit_render.render.canvas import RGBA, Canvas
from fit_render.render.fonts import FontLibrary
from fit_render.render.layout import Placement
from fit_render.units import QuantityFormatter, UnitSystem, formatter_for


@dataclass(frozen=True, slots=True)
class FrameState:
    """What every widget needs to know about the moment being rendered."""

    second: int
    ctx: MetricContext
    units: UnitSystem


@dataclass(frozen=True, slots=True)
class TextStyle:
    font: str
    color: RGBA


class Widget(ABC):
    def __init__(self, placement: Placement) -> None:
        self.placement = placement

    @abstractmethod
    def content(self, frame: FrameState) -> str:
        """The visible state of this widget at `frame`."""

    @abstractmethod
    def draw(self, canvas: Canvas, content: str, fonts: FontLibrary) -> None: ...

    def required_channels(self) -> frozenset[Channel]:
        return frozenset()


class TextWidget(Widget):
    """A widget that renders a single line of text."""

    def __init__(self, placement: Placement, style: TextStyle) -> None:
        super().__init__(placement)
        self.style = style

    def draw(self, canvas: Canvas, content: str, fonts: FontLibrary) -> None:
        if not content:
            return
        xy, anchor, size_px = self.placement.resolve(canvas.width, canvas.height)
        font = fonts.get(self.style.font, size_px)
        canvas.draw_text(content, xy, anchor, font, self.style.color)


class LabelWidget(TextWidget):
    """Static text."""

    def __init__(self, placement: Placement, style: TextStyle, text: str) -> None:
        super().__init__(placement, style)
        self.text = text

    def content(self, frame: FrameState) -> str:
        return self.text


class MetricWidget(TextWidget):
    """'[label] value [unit]' for one metric."""

    def __init__(
        self,
        placement: Placement,
        style: TextStyle,
        metric: Metric,
        label: str | None = None,
        show_unit: bool = True,
        formatter: QuantityFormatter | None = None,
    ) -> None:
        super().__init__(placement, style)
        self.metric = metric
        self.label = label
        self.show_unit = show_unit
        self.formatter = formatter or formatter_for(metric.quantity)

    def content(self, frame: FrameState) -> str:
        value = self.metric.value_at(frame.ctx, frame.second)
        formatted = self.formatter.format(value, frame.units)
        parts = [self.label, formatted.text, formatted.unit if self.show_unit else None]
        return " ".join(part for part in parts if part)

    def required_channels(self) -> frozenset[Channel]:
        return self.metric.required_channels()


class Overlay:
    """The full set of widgets drawn on each frame (Composite)."""

    def __init__(self, widgets: Sequence[Widget], fonts: FontLibrary) -> None:
        self.widgets = tuple(widgets)
        self.fonts = fonts

    def contents(self, frame: FrameState) -> tuple[str, ...]:
        return tuple(widget.content(frame) for widget in self.widgets)

    def draw(self, canvas: Canvas, contents: Sequence[str]) -> None:
        canvas.clear()
        for widget, content in zip(self.widgets, contents, strict=True):
            widget.draw(canvas, content, self.fonts)

    def render(self, canvas: Canvas, frame: FrameState) -> tuple[str, ...]:
        contents = self.contents(frame)
        self.draw(canvas, contents)
        return contents

    def required_channels(self) -> frozenset[Channel]:
        channels: set[Channel] = set()
        for widget in self.widgets:
            channels |= widget.required_channels()
        return frozenset(channels)

    def metrics(self) -> list[Metric]:
        return [w.metric for w in self.widgets if isinstance(w, MetricWidget)]
