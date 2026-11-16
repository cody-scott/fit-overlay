"""Build an Overlay (widget objects) from an OverlaySpec (data). Factory."""

from __future__ import annotations

from collections.abc import Callable

from PIL import ImageColor

from fit_render.errors import SpecError
from fit_render.metrics import Metric, MetricRegistry, SmoothedMetric, default_registry
from fit_render.render.canvas import RGBA
from fit_render.render.fonts import FontLibrary
from fit_render.render.layout import Placement
from fit_render.render.widgets import LabelWidget, MetricWidget, Overlay, TextStyle, Widget
from fit_render.spec import LabelWidgetSpec, MetricWidgetSpec, OverlaySpec, WidgetSpec


def parse_color(value: str) -> RGBA:
    rgba = ImageColor.getcolor(value, "RGBA")
    if not isinstance(rgba, tuple) or len(rgba) != 4:
        raise SpecError(f"Invalid colour {value!r}")
    return (rgba[0], rgba[1], rgba[2], rgba[3])


class OverlayBuilder:
    def __init__(
        self, metrics: MetricRegistry = default_registry, fonts: FontLibrary | None = None
    ) -> None:
        self.metrics = metrics
        self.fonts = fonts or FontLibrary()
        self._factories: dict[type, Callable[[OverlaySpec, WidgetSpec], Widget]] = {
            MetricWidgetSpec: self._metric_widget,
            LabelWidgetSpec: self._label_widget,
        }

    def build(self, spec: OverlaySpec) -> Overlay:
        widgets = [self._factories[type(w)](spec, w) for w in spec.widgets]
        return Overlay(widgets, self.fonts)

    def _style(self, spec: OverlaySpec, widget: WidgetSpec) -> TextStyle:
        font = widget.font or spec.style.font
        if font not in self.fonts:
            raise SpecError(f"Unknown font {font!r}; available: {', '.join(self.fonts.names())}")
        return TextStyle(font=font, color=parse_color(widget.color or spec.style.color))

    @staticmethod
    def _placement(widget: WidgetSpec) -> Placement:
        return Placement(widget.anchor, widget.offset, widget.size)

    def _resolve_metric(self, widget: MetricWidgetSpec) -> Metric:
        try:
            metric = self.metrics.get(widget.metric)
        except KeyError as exc:
            raise SpecError(str(exc.args[0])) from None
        if widget.smoothing_s and widget.smoothing_s > 1:
            metric = SmoothedMetric(metric, widget.smoothing_s)
        return metric

    def _metric_widget(self, spec: OverlaySpec, widget: WidgetSpec) -> Widget:
        assert isinstance(widget, MetricWidgetSpec)
        return MetricWidget(
            self._placement(widget),
            self._style(spec, widget),
            self._resolve_metric(widget),
            label=widget.label,
            show_unit=widget.show_unit,
        )

    def _label_widget(self, spec: OverlaySpec, widget: WidgetSpec) -> Widget:
        assert isinstance(widget, LabelWidgetSpec)
        return LabelWidget(self._placement(widget), self._style(spec, widget), widget.text)
