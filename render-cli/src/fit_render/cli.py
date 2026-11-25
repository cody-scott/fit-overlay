"""fit-render command line. A thin shell over fit_render.pipeline.

Machine-friendly flags (`--json`, `--progress json`) exist so a future API
worker can drive this CLI inside its Docker container and parse the output.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from fit_render import __version__
from fit_render.domain import Channel, Slice, TimelineBuilder, parse_time
from fit_render.domain.slice import format_time
from fit_render.encode import format_for_path
from fit_render.errors import FitRenderError, SpecError
from fit_render.ingest import load_activity
from fit_render.metrics import default_registry
from fit_render.pipeline import NullProgress, PreviewPipeline, ProgressListener, RenderPipeline
from fit_render.render import FontLibrary
from fit_render.schema import overlay_spec_schema_json
from fit_render.spec import (
    FRAME_RATES,
    FRAME_SIZES,
    OutputFormat,
    OverlaySpec,
    apply_overrides,
    list_templates,
    load_spec,
    load_template,
    template_text,
)
from fit_render.units import UnitSystem

app = typer.Typer(
    help="Render transparent data-overlay videos from .fit files.",
    no_args_is_help=True,
    add_completion=False,
)
templates_app = typer.Typer(help="List and show built-in overlay templates.", no_args_is_help=True)
app.add_typer(templates_app, name="templates")

out = Console()
err = Console(stderr=True)


class ProgressMode(StrEnum):
    AUTO = "auto"
    BAR = "bar"
    JSON = "json"
    NONE = "none"


# ---- shared options -------------------------------------------------------

FitArg = Annotated[Path, typer.Argument(help="Activity .fit file.", show_default=False)]
TemplateOpt = Annotated[
    str | None, typer.Option("--template", "-t", help="Built-in template name.")
]
SpecOpt = Annotated[Path | None, typer.Option("--spec", "-s", help="Overlay spec YAML file.")]
SizeOpt = Annotated[
    str | None,
    typer.Option(help=f"Frame size: {', '.join(FRAME_SIZES)} or WIDTHxHEIGHT."),
]
UnitsOpt = Annotated[UnitSystem | None, typer.Option(help="Unit system.")]
WeightOpt = Annotated[float | None, typer.Option("--weight", help="Rider weight in kg.")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]


def _fail(message: str) -> typer.Exit:
    err.print(f"[bold red]error:[/] {message}", highlight=False)
    return typer.Exit(code=1)


def _resolve_spec(template: str | None, spec: Path | None, **overrides: Any) -> OverlaySpec:
    if template and spec:
        raise SpecError("Use either --template or --spec, not both.")
    base = load_spec(spec) if spec else load_template(template or "minimal")
    return apply_overrides(base, **overrides)


def _warn(warnings: list[str]) -> None:
    for warning in warnings:
        err.print(f"[yellow]warning:[/] {warning}", highlight=False)


class RichProgress:
    def __init__(self) -> None:
        self._progress = Progress(
            TextColumn("Rendering"), BarColumn(), TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(), console=err, transient=True,
        )  # fmt: skip
        self._task: Any = None

    def start(self, total: int) -> None:
        self._progress.start()
        self._task = self._progress.add_task("render", total=total)

    def advance(self, done: int) -> None:
        self._progress.update(self._task, completed=done)

    def finish(self) -> None:
        self._progress.stop()


class JsonProgress:
    """One JSON object per line on stderr, at most once per percent."""

    def __init__(self) -> None:
        self._total = 0
        self._last_percent = -1

    def _emit(self, **payload: Any) -> None:
        sys.stderr.write(json.dumps(payload) + "\n")
        sys.stderr.flush()

    def start(self, total: int) -> None:
        self._total = total
        self._emit(event="start", total=total)

    def advance(self, done: int) -> None:
        percent = done * 100 // max(1, self._total)
        if percent != self._last_percent:
            self._last_percent = percent
            self._emit(event="progress", done=done, total=self._total, percent=percent)

    def finish(self) -> None:
        self._emit(event="finish", total=self._total)


def _progress_listener(mode: ProgressMode) -> ProgressListener:
    if mode is ProgressMode.AUTO:
        mode = ProgressMode.BAR if sys.stderr.isatty() else ProgressMode.NONE
    factories: dict[ProgressMode, Callable[[], ProgressListener]] = {
        ProgressMode.BAR: RichProgress,
        ProgressMode.JSON: JsonProgress,
        ProgressMode.NONE: NullProgress,
    }
    return factories[mode]()


# ---- commands --------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
) -> None:
    if version:
        out.print(__version__)
        raise typer.Exit()


@app.command()
def render(
    fit_file: FitArg,
    start: Annotated[str, typer.Option(help="Slice start (H:MM:SS since activity start).")],
    end: Annotated[str, typer.Option(help="Slice end (H:MM:SS since activity start).")],
    output: Annotated[Path, typer.Option("--out", "-o", help="Output file or directory.")],
    template: TemplateOpt = None,
    spec: SpecOpt = None,
    fmt: Annotated[
        OutputFormat | None,
        typer.Option("--format", "-f", help="Output format (default: from --out suffix)."),
    ] = None,
    size: SizeOpt = None,
    fps: Annotated[str | None, typer.Option(help=f"Frame rate: {', '.join(FRAME_RATES)}.")] = None,
    units: UnitsOpt = None,
    weight: WeightOpt = None,
    progress: Annotated[
        ProgressMode, typer.Option(help="Progress output on stderr.")
    ] = ProgressMode.AUTO,
    as_json: JsonOpt = False,
) -> None:
    """Render a slice of an activity to a transparent overlay video."""
    try:
        fmt = fmt or format_for_path(output)
        overlay_spec = _resolve_spec(
            template, spec, size=size, fps=fps, format=fmt, units=units, weight_kg=weight
        )
        result = RenderPipeline().run(
            fit_file, overlay_spec, Slice.parse(start, end), output, _progress_listener(progress)
        )
    except FitRenderError as exc:
        raise _fail(str(exc)) from None
    if as_json:
        print(json.dumps(result.to_dict()))
        return
    _warn(result.warnings)
    out.print(
        f"[green]Wrote[/] {result.output}  ({result.width}x{result.height} @ {result.fps} fps, "
        f"{result.frames} frames, {result.unique_frames} unique, {result.elapsed_s:.1f}s)",
        highlight=False,
    )


@app.command()
def preview(
    fit_file: FitArg,
    at: Annotated[str, typer.Option(help="Moment to render (H:MM:SS since activity start).")],
    output: Annotated[Path, typer.Option("--out", "-o", help="Output PNG path.")] = Path(
        "preview.png"
    ),
    template: TemplateOpt = None,
    spec: SpecOpt = None,
    size: SizeOpt = None,
    units: UnitsOpt = None,
    weight: WeightOpt = None,
) -> None:
    """Render a single frame to PNG to check a layout."""
    try:
        overlay_spec = _resolve_spec(template, spec, size=size, units=units, weight_kg=weight)
        warnings = PreviewPipeline().run(fit_file, overlay_spec, parse_time(at), output)
    except FitRenderError as exc:
        raise _fail(str(exc)) from None
    _warn(warnings)
    out.print(f"[green]Wrote[/] {output}", highlight=False)


@app.command()
def inspect(fit_file: FitArg, as_json: JsonOpt = False) -> None:
    """Summarise an activity file: duration, available data, stops."""
    try:
        activity = load_activity(fit_file)
    except FitRenderError as exc:
        raise _fail(str(exc)) from None
    timeline = TimelineBuilder().build(activity)
    n = timeline.duration_s
    coverage = {
        channel.value: round(100 * sum(v is not None for v in timeline.channels[channel]) / n, 1)
        for channel in Channel
        if channel in timeline.channels
    }
    moving = timeline.moving_seconds_until(n - 1)
    summary: dict[str, Any] = {
        "file": str(fit_file),
        "sport": activity.sport,
        "start_utc": activity.start_time.isoformat(),
        "utc_offset_h": (
            activity.utc_offset.total_seconds() / 3600 if activity.utc_offset is not None else None
        ),
        "duration": format_time(n),
        "duration_s": n,
        "moving_time": format_time(moving),
        "stopped_time": format_time(n - moving),
        "records": len(activity.records),
        "rider_weight_kg": activity.rider_weight_kg,
        "has_gps": activity.has_position,
        "channels_coverage_pct": coverage,
        "notes": list(activity.notes),
    }
    if as_json:
        print(json.dumps(summary))
        return
    table = Table(show_header=False, box=None)
    for key, value in summary.items():
        if key == "channels_coverage_pct":
            value = ", ".join(f"{k} {v}%" for k, v in value.items()) or "none"
        elif key == "notes":
            value = "; ".join(value) or "none"
        table.add_row(f"[bold]{key}[/]", str(value))
    out.print(table)


@app.command()
def metrics() -> None:
    """List metric keys usable in overlay specs."""
    table = Table("key", "label", "quantity", "description")
    for metric in default_registry:
        table.add_row(metric.key, metric.label, metric.quantity.value, metric.description)
    out.print(table)
    out.print(f"Fonts: {', '.join(FontLibrary().names())}")
    out.print(f"Sizes: {', '.join(FRAME_SIZES)}  |  FPS: {', '.join(FRAME_RATES)}")


@app.command()
def schema() -> None:
    """Print the overlay spec JSON Schema (for editors and agents writing specs)."""
    print(overlay_spec_schema_json(), end="")


@templates_app.command("list")
def templates_list() -> None:
    """List built-in templates."""
    for name in list_templates():
        spec = load_template(name)
        out.print(f"[bold]{name:<12}[/] {spec.output.size:<14} {spec.description}")


@templates_app.command("show")
def templates_show(name: str) -> None:
    """Print a template's YAML (redirect to a file to customise it)."""
    try:
        print(template_text(name), end="")
    except FitRenderError as exc:
        raise _fail(str(exc)) from None


if __name__ == "__main__":
    app()
