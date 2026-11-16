"""Locate an ffmpeg binary.

Resolution order: $FFMPEG_PATH, ffmpeg on PATH, then the static build bundled
with the imageio-ffmpeg package (so no system install is required).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fit_render.errors import EncoderError


def find_ffmpeg() -> str:
    explicit = os.environ.get("FFMPEG_PATH")
    if explicit:
        if not Path(explicit).is_file():
            raise EncoderError(f"FFMPEG_PATH={explicit} does not exist")
        return explicit
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as exc:
        raise EncoderError(
            "ffmpeg not found: install it, set FFMPEG_PATH, or install imageio-ffmpeg"
        ) from exc
