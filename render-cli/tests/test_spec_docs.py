"""Keep docs/spec/ (agent-facing spec docs) in sync with the code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fit_render.metrics import default_registry
from fit_render.render import FontLibrary, OverlayBuilder
from fit_render.schema import overlay_spec_schema, overlay_spec_schema_json
from fit_render.spec import load_spec

DOCS = Path(__file__).resolve().parents[1] / "docs" / "spec"
EXAMPLES = sorted((DOCS / "examples").glob("*.yaml"))


def test_schema_file_is_current() -> None:
    committed = (DOCS / "overlay-spec.schema.json").read_text(encoding="utf-8")
    assert committed == overlay_spec_schema_json(), (
        "docs/spec/overlay-spec.schema.json is stale; regenerate with "
        "`uv run fit-render schema > docs/spec/overlay-spec.schema.json`"
    )


def test_schema_lists_metrics_and_fonts() -> None:
    defs = overlay_spec_schema()["$defs"]
    metric_enum = defs["MetricWidgetSpec"]["properties"]["metric"]["enum"]
    assert metric_enum == [m.key for m in default_registry]
    assert defs["TextStyle"]["properties"]["font"]["enum"] == FontLibrary().names()


def test_reference_documents_every_metric() -> None:
    reference = (DOCS / "reference.md").read_text(encoding="utf-8")
    missing = [m.key for m in default_registry if f"| `{m.key}` |" not in reference]
    assert not missing, f"docs/spec/reference.md metric table is missing: {missing}"


def test_examples_exist() -> None:
    assert EXAMPLES


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_builds(path: Path) -> None:
    spec = load_spec(path)
    assert spec.name == path.stem
    OverlayBuilder().build(spec)


def test_schema_is_valid_json() -> None:
    json.loads((DOCS / "overlay-spec.schema.json").read_text(encoding="utf-8"))
