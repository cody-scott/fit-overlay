from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from fit_render.domain import Slice
from fit_render.encode import find_ffmpeg, format_for_path
from fit_render.errors import SliceError, SpecError
from fit_render.pipeline import PreviewPipeline, RenderPipeline
from fit_render.spec import OutputFormat, OverlaySpec, apply_overrides, load_template


def small_spec(fmt: OutputFormat, fps: str = "30") -> OverlaySpec:
    return apply_overrides(load_template("column"), size="320x180", fps=fps, format=fmt)


@pytest.mark.parametrize(
    ("index", "fps", "second"),
    [(0, Fraction(30), 10), (29, Fraction(30), 10), (30, Fraction(30), 11),
     (29, Fraction(30000, 1001), 10), (30, Fraction(30000, 1001), 11),
     (299, Fraction(30000, 1001), 19)],
)  # fmt: skip
def test_second_for_frame(index: int, fps: Fraction, second: int) -> None:
    assert RenderPipeline.second_for_frame(index, Slice(10, 20), fps) == second


def test_format_for_path() -> None:
    assert format_for_path(Path("a.mov")) is OutputFormat.PRORES_4444
    assert format_for_path(Path("a.WEBM")) is OutputFormat.WEBM
    assert format_for_path(Path("frames")) is OutputFormat.PNG_SEQUENCE
    assert format_for_path(Path("a.mp4")) is None


def test_png_sequence(ride_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "frames"
    result = RenderPipeline().run(
        ride_path, small_spec(OutputFormat.PNG_SEQUENCE), Slice(195, 198), out
    )
    files = sorted(out.glob("*.png"))
    assert len(files) == result.frames == 90
    assert result.unique_frames <= 3 + 1  # content changes at most once per second
    assert files[0].read_bytes() == files[29].read_bytes()
    with Image.open(files[0]) as image:
        assert image.size == (320, 180)
        assert image.mode == "RGBA"


def test_output_path_must_match_format(ride_path: Path, tmp_path: Path) -> None:
    with pytest.raises(SpecError, match=r"\.mov"):
        RenderPipeline().run(
            ride_path, small_spec(OutputFormat.PRORES_4444), Slice(0, 2), tmp_path / "x.webm"
        )


def test_slice_errors_surface(ride_path: Path, tmp_path: Path) -> None:
    with pytest.raises(SliceError):
        RenderPipeline().run(
            ride_path, small_spec(OutputFormat.PNG_SEQUENCE), Slice(0, 200), tmp_path / "f"
        )


def test_preview_and_warnings(make_fit, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    fit_path = make_fit(with_power=False, weight_kg=None)
    out = tmp_path / "p.png"
    warnings = PreviewPipeline().run(fit_path, load_template("column"), 100, out)
    assert out.is_file()
    assert any("power" in w for w in warnings)
    assert any("weight" in w for w in warnings)
    with pytest.raises(SliceError):
        PreviewPipeline().run(fit_path, load_template("column"), 600, out)


def _probe(path: Path) -> tuple[str, int]:
    """(stream description, decoded frame count) using ffmpeg only."""
    proc = subprocess.run(
        [find_ffmpeg(), "-hide_banner", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    stream = next(line for line in proc.stderr.splitlines() if "Video:" in line)
    frames = int(re.findall(r"frame=\s*(\d+)", proc.stderr)[-1])
    return stream, frames


@pytest.mark.ffmpeg
@pytest.mark.parametrize(
    ("fmt", "name", "codec", "pix_fmt"),
    [(OutputFormat.PRORES_4444, "out.mov", "prores", "yuva444p"),
     (OutputFormat.WEBM, "out.webm", "vp9", None)],
)  # fmt: skip
def test_video_encoders(
    ride_path: Path, tmp_path: Path, fmt: OutputFormat, name: str, codec: str, pix_fmt: str | None
) -> None:
    out = tmp_path / name
    result = RenderPipeline().run(ride_path, small_spec(fmt, fps="29.97"), Slice(400, 402), out)
    assert result.frames == 60  # round(2 s * 29.97)
    stream, frames = _probe(out)
    assert codec in stream
    if pix_fmt:
        assert pix_fmt in stream
    assert frames == result.frames
    assert not list(tmp_path.glob(".fit-render-*"))  # temp segments cleaned up

    # Decode one frame back (libvpx decoder needed for VP9 alpha) and check transparency.
    png = tmp_path / "decoded.png"
    decoder = ["-c:v", "libvpx-vp9"] if fmt is OutputFormat.WEBM else []
    subprocess.run(
        [find_ffmpeg(), "-hide_banner", "-loglevel", "error", *decoder, "-i", str(out),
         "-frames:v", "1", str(png)],
        check=True,
    )  # fmt: skip
    with Image.open(png) as image:
        alpha = image.convert("RGBA").getchannel("A")
        low, high = alpha.getextrema()
        assert low == 0 and high > 200
