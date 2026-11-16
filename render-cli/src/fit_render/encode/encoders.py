"""Video encoders (Strategy). Each receives straight-alpha RGBA frames in order.

`write(frame, repeat=True)` tells the encoder the frame is identical to the
previous one, letting it skip work (e.g. PNG re-compression).
"""

from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from fractions import Fraction
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

from PIL import Image

from fit_render.encode.ffmpeg import find_ffmpeg
from fit_render.errors import EncoderError


class VideoEncoder(ABC):
    #: expected output suffix ("" means a directory)
    suffix: ClassVar[str]

    def __init__(self, output: Path, width: int, height: int, fps: Fraction) -> None:
        self.output = output
        self.width = width
        self.height = height
        self.fps = fps
        self.frames_written = 0

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def write(self, rgba: bytes, repeat: bool = False) -> None: ...

    @abstractmethod
    def close(self) -> None:
        """Finish the file. Raises EncoderError on failure."""

    def abort(self) -> None:
        """Clean up after an error. Default: just close quietly."""
        with contextlib.suppress(EncoderError):
            self.close()


class FfmpegEncoder(VideoEncoder):
    """Pipes raw RGBA frames to an ffmpeg subprocess."""

    codec_args: ClassVar[tuple[str, ...]]

    def __init__(self, output: Path, width: int, height: int, fps: Fraction) -> None:
        super().__init__(output, width, height, fps)
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr = tempfile.TemporaryFile()  # noqa: SIM115 - lives as long as the encoder

    def command(self, ffmpeg: str) -> list[str]:
        return [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgba",
            "-s", f"{self.width}x{self.height}",
            "-framerate", f"{self.fps.numerator}/{self.fps.denominator}",
            "-i", "-",
            *self.codec_args,
            *self.output_args(),
        ]  # fmt: skip

    def output_args(self) -> list[str]:
        return [str(self.output)]

    def open(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._process = subprocess.Popen(
                self.command(find_ffmpeg()),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr,
            )
        except OSError as exc:
            raise EncoderError(f"Could not start ffmpeg: {exc}") from exc

    def write(self, rgba: bytes, repeat: bool = False) -> None:
        self._pipe(rgba)
        self.frames_written += 1

    def _pipe(self, rgba: bytes) -> None:
        if self._process is None or self._process.stdin is None:
            raise EncoderError("Encoder is not open")
        try:
            self._process.stdin.write(rgba)
        except BrokenPipeError:
            self._process.wait()
            raise EncoderError(f"ffmpeg exited early: {self._error_text()}") from None

    def close(self) -> None:
        if self._process is None:
            return
        process, self._process = self._process, None
        if process.stdin:
            with contextlib.suppress(BrokenPipeError):
                process.stdin.close()
        returncode = process.wait()
        error_text = self._error_text()
        self._stderr.close()
        if returncode != 0:
            raise EncoderError(f"ffmpeg failed ({returncode}): {error_text}")

    def abort(self) -> None:
        if self._process is not None:
            self._process.kill()
            self._process.wait()
            self._process = None
        if not self._stderr.closed:
            self._stderr.close()
        self.output.unlink(missing_ok=True)

    def _error_text(self) -> str:
        self._stderr.seek(0)
        text = self._stderr.read().decode(errors="replace").strip()
        return text[-2000:] or "no error output"


class IntraFrameEncoder(FfmpegEncoder):
    """Fast path for intra-only codecs (every frame is a keyframe, e.g. ProRes).

    Overlay values change once per second, so most frames repeat. Instead of
    encoding every frame, only unique frames are encoded (split into one file per
    frame by ffmpeg's segment muxer); the full-length file is then assembled by
    stream-copying those packets in order with the concat demuxer. Output is
    identical in structure (constant frame rate) at a fraction of the cost.
    """

    container: ClassVar[str]

    def __init__(self, output: Path, width: int, height: int, fps: Fraction) -> None:
        super().__init__(output, width, height, fps)
        self._workdir: Path | None = None
        self._unique = 0
        self._sequence: list[int] = []

    def _segment(self, index: int) -> Path:
        assert self._workdir is not None
        return self._workdir / f"u{index:06d}{self.suffix}"

    def output_args(self) -> list[str]:
        assert self._workdir is not None
        return [
            "-f", "segment", "-segment_time", "0.0001", "-reset_timestamps", "1",
            "-segment_format", self.container,
            str(self._workdir / f"u%06d{self.suffix}"),
        ]  # fmt: skip

    def open(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self._workdir = Path(tempfile.mkdtemp(prefix=".fit-render-", dir=self.output.parent))
        super().open()

    def write(self, rgba: bytes, repeat: bool = False) -> None:
        if not repeat or self._unique == 0:
            self._pipe(rgba)
            self._unique += 1
        self._sequence.append(self._unique - 1)
        self.frames_written += 1

    def close(self) -> None:
        if self._workdir is None:
            return
        try:
            super().close()  # finish encoding the unique frames
            self._assemble()
        finally:
            self._cleanup()

    def abort(self) -> None:
        super().abort()
        self._cleanup()

    def _assemble(self) -> None:
        assert self._workdir is not None
        produced = len(list(self._workdir.glob(f"u*{self.suffix}")))
        if produced != self._unique:
            raise EncoderError(f"Expected {self._unique} encoded frames, ffmpeg wrote {produced}")
        listing = self._workdir / "frames.ffconcat"
        lines = ["ffconcat version 1.0"]
        lines += [f"file '{self._segment(i).name}'" for i in self._sequence]
        listing.write_text("\n".join(lines) + "\n")
        proc = subprocess.run(
            [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", "-f", self.container, str(self.output)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        if proc.returncode != 0:
            self.output.unlink(missing_ok=True)
            raise EncoderError(f"ffmpeg concat failed: {proc.stderr.strip()[-2000:]}")

    def _cleanup(self) -> None:
        if self._workdir is not None:
            shutil.rmtree(self._workdir, ignore_errors=True)
            self._workdir = None


class ProRes4444Encoder(IntraFrameEncoder):
    """ProRes 4444 with alpha in a QuickTime container. Large, but universally
    supported by Premiere Pro, Final Cut Pro and DaVinci Resolve."""

    suffix = ".mov"
    container = "mov"
    codec_args = (
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        "-vendor", "apl0", "-alpha_bits", "16",
    )  # fmt: skip


class WebMEncoder(FfmpegEncoder):
    """VP9 with alpha. Small files; supported by browsers and some editors.
    Inter-frame coding makes repeated frames nearly free, so frames are streamed."""

    suffix = ".webm"
    codec_args = (
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
        "-auto-alt-ref", "0", "-row-mt", "1", "-deadline", "realtime", "-cpu-used", "8",
    )  # fmt: skip


class PngSequenceEncoder(VideoEncoder):
    """A directory of numbered PNGs (frame_000000.png, ...)."""

    suffix = ""

    def __init__(self, output: Path, width: int, height: int, fps: Fraction) -> None:
        super().__init__(output, width, height, fps)
        self._last_png: bytes | None = None

    def open(self) -> None:
        if self.output.exists() and not self.output.is_dir():
            raise EncoderError(f"{self.output} exists and is not a directory")
        self.output.mkdir(parents=True, exist_ok=True)

    def write(self, rgba: bytes, repeat: bool = False) -> None:
        if not repeat or self._last_png is None:
            image = Image.frombytes("RGBA", (self.width, self.height), rgba)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", compress_level=3)
            self._last_png = buffer.getvalue()
        path = self.output / f"frame_{self.frames_written:06d}.png"
        path.write_bytes(self._last_png)
        self.frames_written += 1

    def close(self) -> None:
        return None
