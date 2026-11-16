"""Spec unit: the overlay description format (schema, loading, templates)."""

from fit_render.spec.loader import (
    apply_overrides,
    list_templates,
    load_spec,
    load_template,
    parse_spec,
    template_text,
)
from fit_render.spec.models import (
    FRAME_RATES,
    FRAME_SIZES,
    Anchor,
    LabelWidgetSpec,
    MetricWidgetSpec,
    OutputFormat,
    OutputSpec,
    OverlaySpec,
    RiderSpec,
    TextStyle,
    WidgetSpec,
)

__all__ = [
    "FRAME_RATES",
    "FRAME_SIZES",
    "Anchor",
    "LabelWidgetSpec",
    "MetricWidgetSpec",
    "OutputFormat",
    "OutputSpec",
    "OverlaySpec",
    "RiderSpec",
    "TextStyle",
    "WidgetSpec",
    "apply_overrides",
    "list_templates",
    "load_spec",
    "load_template",
    "parse_spec",
    "template_text",
]
