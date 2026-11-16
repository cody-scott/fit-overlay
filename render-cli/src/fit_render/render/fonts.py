"""Bundled font library. Fonts are referenced by short names in specs."""

from __future__ import annotations

import io
from functools import cache
from importlib import resources

from PIL import ImageFont

from fit_render.errors import SpecError

FontFace = ImageFont.FreeTypeFont

# Monospaced fonts only for now: equal-width digits keep values from jittering.
_FONTS: dict[str, str] = {
    "roboto-mono": "RobotoMono-Regular.ttf",
    "roboto-mono-bold": "RobotoMono-Bold.ttf",
}


@cache
def _font_bytes(filename: str) -> bytes:
    return (resources.files("fit_render.assets.fonts") / filename).read_bytes()


class FontLibrary:
    def __init__(self, fonts: dict[str, str] | None = None) -> None:
        self._fonts = dict(fonts or _FONTS)
        self._cache: dict[tuple[str, int], FontFace] = {}

    def names(self) -> list[str]:
        return sorted(self._fonts)

    def __contains__(self, name: object) -> bool:
        return name in self._fonts

    def get(self, name: str, size_px: int) -> FontFace:
        if name not in self._fonts:
            raise SpecError(f"Unknown font {name!r}; available: {', '.join(self.names())}")
        key = (name, size_px)
        if key not in self._cache:
            data = _font_bytes(self._fonts[name])
            self._cache[key] = ImageFont.truetype(io.BytesIO(data), size_px)
        return self._cache[key]
