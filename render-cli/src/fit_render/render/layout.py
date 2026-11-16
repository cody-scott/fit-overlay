"""Resolve fractional spec positions into pixel coordinates."""

from __future__ import annotations

from dataclasses import dataclass

from fit_render.spec import Anchor

# anchor -> (horizontal side, vertical side); -1 start, 0 centre, 1 end
_SIDES: dict[Anchor, tuple[int, int]] = {
    Anchor.TOP_LEFT: (-1, -1),
    Anchor.TOP: (0, -1),
    Anchor.TOP_RIGHT: (1, -1),
    Anchor.LEFT: (-1, 0),
    Anchor.CENTER: (0, 0),
    Anchor.RIGHT: (1, 0),
    Anchor.BOTTOM_LEFT: (-1, 1),
    Anchor.BOTTOM: (0, 1),
    Anchor.BOTTOM_RIGHT: (1, 1),
}
# Pillow text anchors. Vertical uses font metrics ('a'scender / 'm'iddle /
# 'd'escender), not glyph bounds, so text never shifts as digits change.
_H_ANCHOR = {-1: "l", 0: "m", 1: "r"}
_V_ANCHOR = {-1: "a", 0: "m", 1: "d"}


@dataclass(frozen=True, slots=True)
class Placement:
    anchor: Anchor
    offset: tuple[float, float]
    size: float

    def resolve(self, width: int, height: int) -> tuple[tuple[float, float], str, int]:
        """Return ((x, y), pillow_anchor, font_size_px). Offsets are insets from the
        anchored edge; for centred axes they shift right/down from the centre."""
        h_side, v_side = _SIDES[self.anchor]
        x = self._axis(h_side, self.offset[0], width)
        y = self._axis(v_side, self.offset[1], height)
        anchor = _H_ANCHOR[h_side] + _V_ANCHOR[v_side]
        return (x, y), anchor, max(1, round(self.size * height))

    @staticmethod
    def _axis(side: int, offset: float, extent: int) -> float:
        if side < 0:
            return offset * extent
        if side > 0:
            return extent - offset * extent
        return extent / 2 + offset * extent
