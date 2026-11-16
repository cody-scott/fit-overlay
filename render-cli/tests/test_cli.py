from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fit_render.cli import app

runner = CliRunner()


def test_inspect_json(ride_path: Path) -> None:
    result = runner.invoke(app, ["inspect", str(ride_path), "--json"])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["duration"] == "0:10:00"
    assert summary["moving_time"] == "0:09:00"
    assert summary["channels_coverage_pct"]["power"] == 100.0


def test_templates_show_roundtrip(tmp_path: Path, ride_path: Path) -> None:
    shown = runner.invoke(app, ["templates", "show", "minimal"])
    assert shown.exit_code == 0
    spec = tmp_path / "mine.yaml"
    spec.write_text(shown.stdout)
    out = tmp_path / "frame.png"
    result = runner.invoke(
        app, ["preview", str(ride_path), "--spec", str(spec), "--at", "1:00", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_render_png_sequence_json(ride_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "frames"
    result = runner.invoke(
        app,
        ["render", str(ride_path), "--start", "0:10", "--end", "0:11", "-o", str(out),
         "--size", "320x180", "--progress", "json", "--json"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["format"] == "png-seq"
    assert payload["frames"] == 30
    assert len(list(out.glob("*.png"))) == 30


def test_errors_exit_cleanly(ride_path: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["render", str(ride_path), "--start", "0:00", "--end", "5:00", "-o",
         str(tmp_path / "x.mov")],
    )  # fmt: skip
    assert result.exit_code == 1
    assert "maximum" in result.output
    assert "Traceback" not in result.output

    both = runner.invoke(
        app, ["preview", str(ride_path), "--at", "1", "-t", "minimal", "-s", "x.yaml"]
    )
    assert both.exit_code == 1
