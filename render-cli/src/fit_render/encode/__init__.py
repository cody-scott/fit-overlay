"""Encode unit: write rendered RGBA frames to a transparent video format."""

from fractions import Fraction
from pathlib import Path

from fit_render.encode.encoders import (
    FfmpegEncoder,
    PngSequenceEncoder,
    ProRes4444Encoder,
    VideoEncoder,
    WebMEncoder,
)
from fit_render.encode.ffmpeg import find_ffmpeg
from fit_render.spec import OutputFormat

ENCODERS: dict[OutputFormat, type[VideoEncoder]] = {
    OutputFormat.PRORES_4444: ProRes4444Encoder,
    OutputFormat.WEBM: WebMEncoder,
    OutputFormat.PNG_SEQUENCE: PngSequenceEncoder,
}


def create_encoder(
    fmt: OutputFormat, output: Path, width: int, height: int, fps: Fraction
) -> VideoEncoder:
    return ENCODERS[fmt](output, width, height, fps)


def format_for_path(path: Path) -> OutputFormat | None:
    """Infer the output format from a file suffix (None if ambiguous)."""
    for fmt, encoder in ENCODERS.items():
        if encoder.suffix and path.suffix.lower() == encoder.suffix:
            return fmt
    return OutputFormat.PNG_SEQUENCE if path.suffix == "" else None


__all__ = [
    "ENCODERS",
    "FfmpegEncoder",
    "PngSequenceEncoder",
    "ProRes4444Encoder",
    "VideoEncoder",
    "WebMEncoder",
    "create_encoder",
    "find_ffmpeg",
    "format_for_path",
]
