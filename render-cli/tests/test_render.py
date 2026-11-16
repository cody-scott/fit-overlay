from __future__ import annotations

import io

import pytest
from PIL import Image

from fit_render.metrics import MetricContext
from fit_render.render import FontLibrary, FrameState, OverlayBuilder, PillowCanvas, Placement
from fit_render.spec import Anchor, parse_spec
from fit_render.units import UnitSystem


@pytest.mark.parametrize(
    ("anchor", "xy", "pillow_anchor"),
    [
        (Anchor.TOP_LEFT, (100.0, 50.0), "la"),
        (Anchor.BOTTOM_RIGHT, (900.0, 450.0), "rd"),
        (Anchor.CENTER, (600.0, 300.0), "mm"),
        (Anchor.BOTTOM, (600.0, 450.0), "md"),
    ],
)
def test_placement_resolve(anchor: Anchor, xy: tuple[float, float], pillow_anchor: str) -> None:
    resolved = Placement(anchor, (0.1, 0.1), 0.05).resolve(1000, 500)
    assert resolved == (xy, pillow_anchor, 25)


def _frame(ctx: MetricContext, second: int) -> FrameState:
    return FrameState(second=second, ctx=ctx, units=UnitSystem.METRIC)


def test_widget_contents(ctx: MetricContext) -> None:
    spec = parse_spec(
        {"widgets": [
            {"metric": "heart_rate", "label": "HR"},
            {"metric": "speed", "show_unit": False},
            {"type": "label", "text": "KOM attempt"},
        ]}
    )  # fmt: skip
    overlay = OverlayBuilder().build(spec)
    assert overlay.contents(_frame(ctx, 50)) == ("HR 125 bpm", "28.8", "KOM attempt")
    assert overlay.contents(_frame(ctx, 305))[0] == "HR -- bpm"


def test_rendered_frame_is_transparent_with_clean_text(ctx: MetricContext) -> None:
    spec = parse_spec({"output": {"size": "720p"}, "widgets": [{"metric": "power", "size": 0.1}]})
    canvas = PillowCanvas(*spec.output.resolution)
    OverlayBuilder().build(spec).render(canvas, _frame(ctx, 50))
    image = Image.open(io.BytesIO(canvas.png_bytes()))
    assert image.mode == "RGBA"
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    assert bbox is not None
    left, top, right, bottom = bbox
    assert left >= 1280 * 0.03 - 2 and top >= 720 * 0.03 - 2  # top-left placement
    assert right < 640 and bottom < 360
    assert alpha.getpixel((1279, 719)) == 0  # background fully transparent
    # Anti-aliased edge pixels keep the text colour (straight alpha, no dark fringe).
    rgb_on_edges = {
        image.getpixel((x, y))[:3]
        for x in range(left, right)
        for y in range(top, bottom)
        if 0 < image.getpixel((x, y))[3] < 255
    }
    assert rgb_on_edges == {(255, 255, 255)}


@pytest.mark.parametrize("font", FontLibrary().names())
def test_bundled_fonts_have_equal_width_digits(font: str) -> None:
    """Values must not jiggle as digits change: every digit has the same advance."""
    face = FontLibrary().get(font, 48)
    widths = {face.getlength(f"{d}{d}{d} W") for d in "0123456789-"}
    assert len(widths) == 1
