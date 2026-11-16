"""Drawing surface abstraction (Bridge): widgets draw on a Canvas, never on Pillow
directly, so the backend (Pillow today, Skia/Cairo later) can be swapped."""

from __future__ import annotations

import io
from abc import ABC, abstractmethod

from PIL import Image, ImageDraw

from fit_render.render.fonts import FontFace

RGBA = tuple[int, int, int, int]


class Canvas(ABC):
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    @abstractmethod
    def clear(self) -> None:
        """Reset to fully transparent."""

    @abstractmethod
    def draw_text(
        self, text: str, xy: tuple[float, float], anchor: str, font: FontFace, color: RGBA
    ) -> None:
        """Draw text. `anchor` is a two-letter Pillow-style anchor (e.g. 'ld')."""

    @abstractmethod
    def rgba_bytes(self) -> bytes:
        """Raw straight-alpha RGBA pixels, row-major."""

    @abstractmethod
    def png_bytes(self) -> bytes: ...


class PillowCanvas(Canvas):
    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height)
        self._image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self._draw = ImageDraw.Draw(self._image)

    def clear(self) -> None:
        self._image.paste((0, 0, 0, 0), (0, 0, self.width, self.height))

    def draw_text(
        self, text: str, xy: tuple[float, float], anchor: str, font: FontFace, color: RGBA
    ) -> None:
        self._draw.text(xy, text, fill=color, font=font, anchor=anchor)

    def rgba_bytes(self) -> bytes:
        return self._image.tobytes()

    def png_bytes(self) -> bytes:
        buffer = io.BytesIO()
        self._image.save(buffer, format="PNG", optimize=False, compress_level=3)
        return buffer.getvalue()
