"""End-to-end pipelines: FIT file + spec (+ slice) -> image or video.

OverlayPipeline holds the shared preparation steps (load -> timeline -> metrics
context -> overlay); RenderPipeline and PreviewPipeline add their own output step.
This module is the package's programmatic API; the CLI is a thin shell over it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from fit_render.domain import Activity, Slice, Timeline, TimelineBuilder
from fit_render.domain.slice import format_time
from fit_render.encode import ENCODERS, create_encoder
from fit_render.errors import SliceError, SpecError
from fit_render.ingest import load_activity
from fit_render.metrics import MetricContext, PowerToWeightMetric
from fit_render.render import FrameState, Overlay, OverlayBuilder, PillowCanvas
from fit_render.spec import OutputFormat, OverlaySpec


class ProgressListener(Protocol):
    """Observer notified as frames are produced."""

    def start(self, total: int) -> None: ...
    def advance(self, done: int) -> None: ...
    def finish(self) -> None: ...


class NullProgress:
    def start(self, total: int) -> None: ...
    def advance(self, done: int) -> None: ...
    def finish(self) -> None: ...


@dataclass(frozen=True)
class PreparedOverlay:
    spec: OverlaySpec
    activity: Activity
    timeline: Timeline
    ctx: MetricContext
    overlay: Overlay
    warnings: list[str]

    def frame(self, second: int) -> FrameState:
        return FrameState(second=second, ctx=self.ctx, units=self.spec.units)


@dataclass
class RenderResult:
    output: Path
    format: OutputFormat
    width: int
    height: int
    fps: str
    start: str
    end: str
    frames: int
    unique_frames: int
    elapsed_s: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": str(self.output),
            "format": self.format.value,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "start": self.start,
            "end": self.end,
            "frames": self.frames,
            "unique_frames": self.unique_frames,
            "elapsed_s": round(self.elapsed_s, 3),
            "warnings": self.warnings,
        }


class OverlayPipeline:
    """Shared preparation steps. Subclasses add the output step."""

    def __init__(
        self,
        builder: OverlayBuilder | None = None,
        timeline_builder: TimelineBuilder | None = None,
    ) -> None:
        self.builder = builder or OverlayBuilder()
        self.timeline_builder = timeline_builder or TimelineBuilder()

    def prepare(self, fit_path: Path, spec: OverlaySpec) -> PreparedOverlay:
        overlay = self.builder.build(spec)  # validate the spec before parsing the file
        activity = load_activity(fit_path)
        timeline = self.timeline_builder.build(activity)
        weight = spec.rider.weight_kg or activity.rider_weight_kg
        ctx = MetricContext(timeline=timeline, rider_weight_kg=weight)
        warnings = self._data_warnings(activity, overlay, weight)
        return PreparedOverlay(spec, activity, timeline, ctx, overlay, warnings)

    @staticmethod
    def _data_warnings(activity: Activity, overlay: Overlay, weight: float | None) -> list[str]:
        warnings = list(activity.notes)
        missing = overlay.required_channels() - activity.channels_present()
        for channel in sorted(missing):
            warnings.append(f"No {channel.value} data in this file; those widgets will show --")
        uses_weight = any(
            isinstance(link, PowerToWeightMetric)
            for metric in overlay.metrics()
            for link in metric.chain()
        )
        if uses_weight and not weight:
            warnings.append("No rider weight (set rider.weight_kg or --weight); W/kg will show --")
        return warnings

    @staticmethod
    def canvas_for(spec: OverlaySpec) -> PillowCanvas:
        width, height = spec.output.resolution
        return PillowCanvas(width, height)


class PreviewPipeline(OverlayPipeline):
    """Render a single frame to PNG, for quick layout checks."""

    def run(self, fit_path: Path, spec: OverlaySpec, at_s: int, output: Path) -> list[str]:
        prepared = self.prepare(fit_path, spec)
        if not 0 <= at_s < prepared.timeline.duration_s:
            raise SliceError(
                f"--at {format_time(at_s)} is outside the activity "
                f"(0:00:00 - {format_time(prepared.timeline.duration_s - 1)})"
            )
        canvas = self.canvas_for(spec)
        prepared.overlay.render(canvas, prepared.frame(at_s))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(canvas.png_bytes())
        return prepared.warnings


class RenderPipeline(OverlayPipeline):
    """Render a slice to a transparent video (or PNG sequence)."""

    def run(
        self,
        fit_path: Path,
        spec: OverlaySpec,
        slice_: Slice,
        output: Path,
        progress: ProgressListener | None = None,
    ) -> RenderResult:
        progress = progress or NullProgress()
        started = time.perf_counter()
        fmt = spec.output.format
        self._check_output_path(output, fmt)
        prepared = self.prepare(fit_path, spec)
        warnings = slice_.validate(prepared.timeline.duration_s) + prepared.warnings

        width, height = spec.output.resolution
        fps = spec.output.frame_rate
        total_frames = round(slice_.duration_s * fps)
        canvas = self.canvas_for(spec)
        unique = 0
        last_contents: tuple[str, ...] | None = None
        frame_bytes = b""

        progress.start(total_frames)
        with create_encoder(fmt, output, width, height, fps) as encoder:
            for index in range(total_frames):
                second = self.second_for_frame(index, slice_, fps)
                contents = prepared.overlay.contents(prepared.frame(second))
                repeat = contents == last_contents
                if not repeat:
                    prepared.overlay.draw(canvas, contents)
                    frame_bytes = canvas.rgba_bytes()
                    last_contents = contents
                    unique += 1
                encoder.write(frame_bytes, repeat=repeat)
                progress.advance(index + 1)
        progress.finish()

        return RenderResult(
            output=output,
            format=fmt,
            width=width,
            height=height,
            fps=spec.output.fps,
            start=format_time(slice_.start_s),
            end=format_time(slice_.end_s),
            frames=total_frames,
            unique_frames=unique,
            elapsed_s=time.perf_counter() - started,
            warnings=warnings,
        )

    @staticmethod
    def second_for_frame(index: int, slice_: Slice, fps: Fraction) -> int:
        """Activity second shown on frame `index` (exact rational arithmetic, so
        29.97 fps never drifts)."""
        offset = (index * fps.denominator) // fps.numerator
        return min(slice_.start_s + offset, slice_.end_s - 1)

    @staticmethod
    def _check_output_path(output: Path, fmt: OutputFormat) -> None:
        suffix = ENCODERS[fmt].suffix
        if suffix and output.suffix.lower() != suffix:
            raise SpecError(f"Format {fmt.value} writes {suffix} files; got {output.name!r}")
        if not suffix and output.suffix:
            raise SpecError(f"Format {fmt.value} writes a directory; got {output.name!r}")
