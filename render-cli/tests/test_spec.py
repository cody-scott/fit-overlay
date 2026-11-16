from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from fit_render.errors import SpecError
from fit_render.render import OverlayBuilder
from fit_render.spec import (
    OutputFormat,
    apply_overrides,
    list_templates,
    load_spec,
    load_template,
    parse_spec,
)
from fit_render.units import UnitSystem

MINIMAL = {"widgets": [{"type": "metric", "metric": "power"}]}


def test_builtin_templates_load_and_build() -> None:
    names = list_templates()
    assert {"minimal", "column", "bottom-bar", "vertical"} <= set(names)
    for name in names:
        spec = load_template(name)
        assert spec.name == name
        OverlayBuilder().build(spec)  # every metric and font resolves


def test_defaults() -> None:
    spec = parse_spec(MINIMAL)
    assert spec.output.resolution == (1920, 1080)
    assert spec.output.frame_rate == 30
    assert spec.output.format is OutputFormat.PRORES_4444
    assert spec.units is UnitSystem.METRIC


def test_fps_accepts_numbers_and_ntsc_rates() -> None:
    spec = parse_spec({**MINIMAL, "output": {"fps": 29.97}})
    assert spec.output.frame_rate == Fraction(30000, 1001)


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"output": {"size": "999p"}}, "Unknown size"),
        ({"output": {"size": "1921x1080"}}, "even"),
        ({"output": {"fps": "31"}}, "Unsupported fps"),
        ({"style": {"color": "white"}}, "Color"),
        ({"widgets": []}, "widgets"),
        ({"widgets": [{"type": "metric", "metric": "power", "offset": [2, 0]}]}, "offset"),
        ({"widgets": [{"type": "gauge"}]}, "widgets"),
        ({"bogus": 1}, "bogus"),
    ],
)
def test_invalid_specs(patch: dict[str, object], message: str) -> None:
    with pytest.raises(SpecError, match=message):
        parse_spec({**MINIMAL, **patch})


def test_unknown_metric_or_font_fails_at_build() -> None:
    with pytest.raises(SpecError, match="Unknown metric"):
        OverlayBuilder().build(parse_spec({"widgets": [{"metric": "watts"}]}))
    with pytest.raises(SpecError, match="Unknown font"):
        OverlayBuilder().build(parse_spec({**MINIMAL, "style": {"font": "comic-sans"}}))


def test_overrides() -> None:
    spec = apply_overrides(
        load_template("minimal"), size="4k", fps="60", format=OutputFormat.WEBM,
        units=UnitSystem.IMPERIAL, weight_kg=80.0,
    )  # fmt: skip
    assert spec.output.resolution == (3840, 2160)
    assert spec.output.fps == "60"
    assert spec.output.format is OutputFormat.WEBM
    assert spec.units is UnitSystem.IMPERIAL
    assert spec.rider.weight_kg == 80.0
    with pytest.raises(SpecError):
        apply_overrides(spec, size="bad")


def test_load_spec_file(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text("widgets:\n  - {metric: heart_rate, label: HR}\n")
    assert load_spec(path).widgets[0].label == "HR"  # type: ignore[union-attr]
    path.write_text("widgets: [unclosed\n")
    with pytest.raises(SpecError, match="YAML"):
        load_spec(path)
    with pytest.raises(SpecError, match="Cannot read"):
        load_spec(tmp_path / "missing.yaml")
    with pytest.raises(SpecError, match="Unknown template"):
        load_template("nope")
