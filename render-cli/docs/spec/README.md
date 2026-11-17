# Writing overlay specs — guide for agents

An **overlay spec** is a YAML file that tells `fit-render` what to draw and where.
Built-in **templates** are the same thing, shipped in `src/fit_render/templates/`.
This folder has everything you need to write one without reading the source.

| File | Use it for |
|---|---|
| [`reference.md`](reference.md) | Every field, allowed value, default and validation rule. Metric catalogue with example output. |
| [`layout.md`](layout.md) | Placement geometry: anchors, offsets, text size, how wide a value is, how to stack rows without overlap. |
| [`overlay-spec.schema.json`](overlay-spec.schema.json) | JSON Schema (generated: `fit-render schema`). Validate against it, or point your editor at it. |
| [`examples/`](examples/) | Annotated, tested specs: `corner-stack` (16:9, labels, stacked rows), `race-hud` (4K, imperial, colour overrides, title), `phone-grid` (9:16, two columns with captions). |

The built-in templates (`fit-render templates show <name>`) are also good starting points:
`minimal`, `column`, `bottom-bar`, `vertical`.

## Workflow

1. **Pin down the brief.** Ask (or infer) these. They decide the whole layout:
   - Frame size and fps of the footage. The overlay must match it (`output.size`, `output.fps`).
     Changing the **aspect ratio** later breaks horizontal spacing (see `layout.md`).
   - Which metrics, and how prominent each one is.
   - Units (`metric`/`imperial`). Rider weight if `power_to_weight` is shown.
   - Where the busy parts of the footage are (bars, a GPS unit, the road), so the text avoids them.
2. **Check the data has the channels.** `fit-render inspect ride.fit --json` →
   `channels_coverage_pct`. A metric whose channel is missing renders `--` for the whole clip.
   Requirements are in the metric table in `reference.md` (e.g. `gradient` needs altitude **and**
   distance; indoor rides usually have no altitude).
3. **Start from the closest template or example**, e.g.
   `fit-render templates show column > my-overlay.yaml`.
4. **Lay it out with the numbers in `layout.md`.** Work out row pitch and the widest text for
   each widget (use the worst-case widths, not the value you see in one frame).
5. **Validate.** Structure: the JSON Schema. Full check (metrics, fonts, colours), no FIT file needed:
   ```bash
   uv run python -c "from pathlib import Path; from fit_render.spec import load_spec; \
   from fit_render.render import OverlayBuilder; OverlayBuilder().build(load_spec(Path('my-overlay.yaml')))"
   ```
   Errors are plain messages listing the bad field, e.g. `widgets.2.metric.offset: Value error, offset values must be between 0 and 1`.
6. **Preview frames and look at them.**
   ```bash
   fit-render preview ride.fit --spec my-overlay.yaml --at 7:30 -o frame.png
   ```
   No FIT file to hand? `uv run python tests/fitgen.py /tmp/ride.fit` writes a synthetic 600 s
   ride (has power, HR, speed, cadence, altitude, distance; stop at 200–260 s, HR dropout at 300 s,
   5 % climb 400–500 s). Add `--weight 72` if the spec shows W/kg without `rider.weight_kg`.

   The PNG is **white text on a transparent background**; most image viewers show it on white,
   so it looks empty. Composite it onto a dark colour before you look at it:
   ```bash
   uv run python -c "import sys; from PIL import Image; im=Image.open(sys.argv[1]).convert('RGBA'); \
   bg=Image.new('RGBA', im.size, (60,90,60,255)); bg.alpha_composite(im); bg.convert('RGB').save(sys.argv[2])" \
   frame.png frame-bg.png
   ```
   Check several moments: a hard effort (widest values), a stop (`0`, `--`), and missing data.
7. **Render a short clip** if timing matters: `fit-render render ride.fit --spec my-overlay.yaml
   --start 7:30 --end 7:35 -o clip.webm`.

## Rules that catch people out

- Positions and sizes are **fractions of the frame**, never pixels. `offset` is an *inset* from the
  anchored edge, not an x/y coordinate. Both values must be in `[0, 1]`. On a centred axis
  (`top`, `bottom`, `center`, `left`, `right`) the offset only moves the text right/down.
- `size` is the font size as a fraction of frame **height**. The visible line is ~1.32 × `size` tall.
- The **anchor also aligns the text**: `*-right` anchors right-align, so values grow to the left.
  Use right anchors for columns on the right so units line up.
- Unknown keys are errors (`extra="forbid"`). There's no `x`, `y`, `position`, `width`, `align`, etc.
- Quote `fps` (`"29.97"`). Colours are `#RGB`, `#RRGGBB` or `#RRGGBBAA` (the last pair is opacity).
- `label` on a metric widget is free text drawn before the value (`HR 165 bpm`). Nothing is added
  automatically; omit it for a bare value.
- `type` defaults to `metric`, so `{ metric: speed }` is a complete widget.
- `smoothing_s` is a trailing average. `power_3s` is already smoothed; use `smoothing_s: 3–5` on
  `power_to_weight` and `gradient` so they don't flicker.
- Values update once per second. Text is drawn as-is: no outline, shadow or background panel
  (yet; see `PLAN.md` M9). Pick placements over calm parts of the footage.
- Only monospaced fonts are bundled (`roboto-mono`, `roboto-mono-bold`), so digits don't jiggle and
  widths are predictable.

## Adding a built-in template

1. Save it as `src/fit_render/templates/<name>.yaml` with `name: <name>` (must match the file name)
   and a one-line `description` (shown by `templates list`).
2. House style: one widget per line in flow style, columns aligned; `fps` quoted; no
   `rider.weight_kg` (the user supplies it).
3. `uv run pytest tests/test_spec.py` builds every template.

## Keeping these docs current

When the spec schema changes (new widget type, style option, metric, font), update
`reference.md`/`layout.md`, add or adjust an example, and regenerate the schema:
`uv run fit-render schema > docs/spec/overlay-spec.schema.json`. `tests/test_spec_docs.py`
fails if the schema file is stale or an example no longer builds.
