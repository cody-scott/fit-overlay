"""Load specs from YAML files or built-in templates, and apply CLI overrides."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fit_render.errors import SpecError
from fit_render.spec.models import OverlaySpec

_TEMPLATE_PACKAGE = "fit_render.templates"


def parse_spec(data: Any, source: str = "spec") -> OverlaySpec:
    if not isinstance(data, dict):
        raise SpecError(f"{source}: top level must be a mapping")
    try:
        return OverlaySpec.model_validate(data)
    except ValidationError as exc:
        lines = [f"{source} is invalid:"]
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            lines.append(f"  - {location}: {error['msg']}")
        raise SpecError("\n".join(lines)) from None


def _parse_yaml(text: str, source: str) -> OverlaySpec:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"{source}: invalid YAML: {exc}") from None
    return parse_spec(data, source)


def load_spec(path: Path) -> OverlaySpec:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"Cannot read spec {path}: {exc.strerror}") from None
    return _parse_yaml(text, path.name)


def list_templates() -> list[str]:
    root = resources.files(_TEMPLATE_PACKAGE)
    return sorted(
        entry.name.removesuffix(".yaml") for entry in root.iterdir() if entry.name.endswith(".yaml")
    )


def template_text(name: str) -> str:
    resource = resources.files(_TEMPLATE_PACKAGE) / f"{name}.yaml"
    if not resource.is_file():
        raise SpecError(f"Unknown template {name!r}; available: {', '.join(list_templates())}")
    return resource.read_text(encoding="utf-8")


def load_template(name: str) -> OverlaySpec:
    return _parse_yaml(template_text(name), f"template '{name}'")


def apply_overrides(spec: OverlaySpec, **overrides: Any) -> OverlaySpec:
    """Return a copy with CLI overrides applied. Keys: size, fps, format, units, weight_kg.
    None values are ignored. Re-validates so overrides get the same checks as the file."""
    data = spec.model_dump(mode="json")
    output_keys = {"size", "fps", "format"}
    for key, value in overrides.items():
        if value is None:
            continue
        if key in output_keys:
            data["output"][key] = str(value)
        elif key == "units":
            data["units"] = str(value)
        elif key == "weight_kg":
            data["rider"]["weight_kg"] = value
        else:
            raise ValueError(f"Unknown override {key!r}")
    return parse_spec(data, "overrides")
