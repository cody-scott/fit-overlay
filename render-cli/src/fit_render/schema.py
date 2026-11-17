"""JSON Schema for overlay specs, for editors, agents and the future web UI.

The Pydantic model in `spec` is the source of truth for structure. It cannot list
metric keys or font names (those live in higher layers), so this module adds them
as enums. It sits at the top level, like `pipeline.py`, because it reads from
`spec`, `metrics` and `render`.

`docs/spec/overlay-spec.schema.json` is generated from this; a test keeps it in sync.
"""

from __future__ import annotations

import json
from typing import Any

from fit_render.metrics import default_registry
from fit_render.render import FontLibrary
from fit_render.spec import FRAME_RATES, FRAME_SIZES, OverlaySpec

_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
_CUSTOM_SIZE_PATTERN = r"^\d{2,5}x\d{2,5}$"
_WIDGETS = ("MetricWidgetSpec", "LabelWidgetSpec")


def _color(description: str, nullable: bool) -> dict[str, Any]:
    color: dict[str, Any] = {"type": "string", "pattern": _COLOR_PATTERN}
    if not nullable:
        return {**color, "description": description}
    return {"anyOf": [color, {"type": "null"}], "default": None, "description": description}


def _font(description: str, nullable: bool) -> dict[str, Any]:
    font: dict[str, Any] = {"type": "string", "enum": FontLibrary().names()}
    if not nullable:
        return {**font, "description": description}
    return {"anyOf": [font, {"type": "null"}], "default": None, "description": description}


def overlay_spec_schema() -> dict[str, Any]:
    schema = OverlaySpec.model_json_schema()
    defs = schema["$defs"]

    output = defs["OutputSpec"]["properties"]
    output["size"] = {
        "default": output["size"]["default"],
        "description": "Frame size preset, or a custom even WIDTHxHEIGHT (e.g. '3000x2000').",
        "anyOf": [
            {"type": "string", "enum": list(FRAME_SIZES)},
            {"type": "string", "pattern": _CUSTOM_SIZE_PATTERN},
        ],
    }
    output["fps"] = {
        "default": output["fps"]["default"],
        "description": "Frame rate. Quote it in YAML ('29.97', '30').",
        "type": "string",
        "enum": list(FRAME_RATES),
    }

    style = defs["TextStyle"]["properties"]
    style["font"] = {
        **_font("Default font for every widget.", False),
        "default": style["font"]["default"],
    }
    style["color"] = {
        **_color("Default text colour for every widget.", False),
        "default": style["color"]["default"],
    }

    for name in _WIDGETS:
        props = defs[name]["properties"]
        props["font"] = _font("Overrides style.font for this widget.", True)
        props["color"] = _color("Overrides style.color for this widget.", True)

    metric = defs["MetricWidgetSpec"]["properties"]["metric"]
    metric["enum"] = [m.key for m in default_registry]
    metric["description"] = "Metric key (see `fit-render metrics`)."

    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["description"] = (
        "fit-render overlay spec (version 1). Positions and sizes are fractions of the frame."
    )
    return schema


def overlay_spec_schema_json() -> str:
    return json.dumps(overlay_spec_schema(), indent=2) + "\n"
