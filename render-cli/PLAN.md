# render-cli — next phase plan

Scope: `render-cli/` only. The CLI stays a dumb renderer: **everything is driven by the
spec**. No event-type logic (race, training, etc.). Whatever the spec describes, we draw.

## Decisions (from planning session, 2026-11-17)

| Topic | Decision |
|---|---|
| Biggest gap | Context over time: graphs come first. |
| Graph model | **One generic `graph` widget**. The elevation profile and the sparkline are just configurations of it. Templates ship ready-made presets. |
| Profile | X = distance, filled area, travelled part highlighted, moving dot. Range is configurable (default: whole ride). |
| Sparkline | Same widget, any metric. The spec chooses the range (trailing N s, clip, or whole course) and the Y range (fixed `[min, max]` or `auto`). |
| Motion | Marker moves in **1 Hz steps** (keeps frame de-duplication). No per-frame interpolation. |
| Climb stats | Not now ("just the graph"). |
| Legibility | Text **outline + drop shadow**, configured in the spec (spec-level default, per-widget override). Also applies to graph lines. |
| Aggregates | Generic `min` / `max` / `avg` of any metric over a window, configured in the spec. |
| Zones | **Deferred.** No zone colouring this phase. |
| Order | Graph + profile → sparkline → outline/shadow → aggregates. Each one gets its own feature branch and PR. |

## Spec shape (target)

```yaml
widgets:
  # elevation profile
  - type: graph
    metric: elevation
    x_axis: distance          # distance | time
    range: ride               # ride | clip | {trailing_s: 30} | {start: "0:10:00", end: "0:40:00"}
    y_range: auto             # auto | [min, max]   (display units)
    fill: true
    marker: dot               # dot | none
    ahead: dim                # show | dim | hide   (part of the range not yet reached)
    anchor: bottom-right
    offset: [0.03, 0.04]
    box: [0.30, 0.10]         # width, height as fractions of the frame
    line_width: 0.004         # fraction of frame height
  # power sparkline
  - type: graph
    metric: power_3s
    x_axis: time
    range: { trailing_s: 30 }
    y_range: [0, 1200]
  # aggregate on a normal metric widget
  - { type: metric, metric: power, agg: max, window: clip, label: MAX }

style:
  font: roboto-mono-bold
  color: "#FFFFFF"
  outline: { width: 0.06, color: "#000000" }              # width = fraction of text size
  shadow:  { offset: [0.03, 0.03], blur: 0.05, color: "#000000", opacity: 0.6 }
```

Positions and sizes are always frame fractions, never pixels (existing rule).

---

## M7 — Graph widget foundation + elevation profile  (`feature/graph-widget`)

**Plumbing**
- [ ] `Canvas`: add `draw_polyline`, `draw_polygon`, `draw_ellipse`, `paste_layer`. Pillow lines
      aren't anti-aliased, so render graph layers supersampled (e.g. 4×) and downsample.
      Check that downsampling keeps **straight alpha** with the line colour on the edges.
- [ ] `FrameState` / `MetricContext` learn the **clip** (`slice.start_s`, `end_s`), which `range: clip`
      and M10's `window: clip` both need. `preview` gets an optional `--clip-start` (default: the preview second).
- [ ] Layout: `Placement` supports a **box** (w, h) as well as the text `size`, with the same anchor/offset rules.

**Series**
- [ ] `SeriesSampler` (in `render/` or a new `series/` subpackage; it depends on `metrics` and `domain` only):
      metric + x_axis + range → list of `(x, y | None)` points, bucketed to the box's pixel width.
  - `x_axis: distance` collapses stopped seconds (distance holds, so no flat stop sections).
    Missing distance channel → typed `SpecError` ("graph x_axis=distance needs distance data").
  - `range: {start, end}` is validated against the ride duration (`SliceError` style message).
  - `None` breaks the line into segments; it is not interpolated.
- [ ] `y_range: auto` is computed **once** over everything the graph can show during this render
      (so the scale never jumps). `y_range` values are in **display units** (W, km/h, or mph if imperial).

**Widget**
- [ ] `GraphWidgetSpec` (`Tag("graph")`) + `GraphWidget` + an `OverlayBuilder` factory entry.
- [ ] The static geometry (line, fill) is pre-rendered **once** into an RGBA layer at build time.
      Each frame only adds the marker and the `ahead` dimming on top.
- [ ] `content()` = the marker's **pixel** position plus the `ahead` cut-off pixel, so frames de-dup even better than
      once per second. The marker is hidden when the value is missing.
- [ ] New template `climb.yaml` (profile bottom-right + power/HR/speed/gradient text).

**Tests**
- [ ] Sampler over the `fitgen` ride: the 5 % climb at 400–500 s shows up as a rising segment, and the
      60 s auto-pause adds no distance points.
- [ ] Marker x is monotonic over the slice, and `content()` changes only when the pixel moves.
- [ ] Alpha test on graph edges (straight alpha, line colour kept).
- [ ] Missing-distance error is clean (CLI exit 1, no traceback).
- [ ] The `ffmpeg` render test with `climb.yaml` checks the frame count and alpha. `test_spec` builds the new template.
- [ ] Real fixture (TrainerRoad, no GPS distance?) behaves sensibly. Check whether it has distance.

## M8 — Sparkline mode  (`feature/graph-sparkline`)

- [ ] `range: {trailing_s: N}`: the window ends at the current second. Seconds before the ride start are blank.
      This is a dynamic graph, so the line is drawn per unique frame (≈ once per second). No static layer.
- [ ] `range: ride|clip|{start,end}` with `x_axis: time` gives a "whole course" power/HR graph that reuses the M7 static layer + `ahead`.
- [ ] `fill` optional; `marker` defaults to `none` for trailing windows.
- [ ] `content()` for a trailing window = the bucketed values in the window (a cheap string).
- [ ] Optional: add a sparkline to `column.yaml` or a new template.
- [ ] Tests: the window slides one second per second, the fixed `y_range` clamps out-of-range values, `auto` stays stable
      across the clip, and missing HR (the dropout at 300 s) breaks the line.

## M9 — Outline + drop shadow  (`feature/text-effects`)

- [ ] Spec: `style.outline`, `style.shadow` (spec-level), overridable per widget (`outline: null` turns it off).
      Sizes are fractions of the text size (or of the line width for graphs).
- [ ] Text outline uses Pillow's `stroke_width` / `stroke_fill`. Graph outline draws a wider stroke underneath.
- [ ] Shadow: draw onto a separate layer, Gaussian-blur only the widget's bbox, composite it underneath.
- [ ] **Update the alpha rule.** With effects on, edge pixels legitimately mix text and outline colours. Keep the
      existing test for effect-free widgets. Add composite-over-black/white tests for effects.
- [ ] Update the `docs/PLAN.md` styling decision ("no outline/shadow" → spec-driven outline/shadow).
- [ ] Check the render-time cost on 4K ProRes. Blur runs only on unique frames.

## M10 — Aggregate metrics  (`feature/aggregate-metrics`)

- [ ] `AggregateMetric(CompositeMetric)`: `fn ∈ {min, max, avg}`, `window ∈ {clip, ride, <int seconds>}`.
- [ ] Spec: `agg` + `window` fields on `MetricWidgetSpec` (validated together; they compose with `smoothing_s`:
      smooth first, then aggregate, so "max 3 s power in the clip" works).
- [ ] Precompute prefix arrays once per render (`ride` windows over a 7 h 51 m ride must not be O(n) per frame).
- [ ] Default label suffix/prefix (e.g. `MAX`, `AVG`) when no `label` is given.
- [ ] Tests: max power over the clip is monotonic, avg ignores missing data, and the trailing window equals the brute force result.

## Cross-cutting (every milestone)

- `ruff format`, `ruff check`, `mypy --strict`, `pytest` all pass.
- README + `render-cli/AGENTS.md` "Extending" / "must not regress" sections updated.
- The CLI JSON contract is unchanged. A new widget type is additive. Consider listing widget types in `--help`.
- Layering: the new code respects `domain`/`units` → `metrics` → `spec` → `render`. Nothing imports `cli`.

## Open questions (confirm before or during the relevant milestone)

1. **Aggregate windows:** the plan assumes all three (`clip`, `ride`, trailing N s) + `min`/`max`/`avg`. OK?
2. **`avg` while stopped:** include the stopped-time zeros for power/speed, or average moving seconds only?
3. **`y_range` units:** display units (proposed) or SI?
4. Does the real TrainerRoad fixture have a distance channel? If not, the profile on indoor rides needs `x_axis: time`.

## Deferred / later

Zone colouring (FTP / max HR in spec), gauges and bars, minimap, climb stats (distance and elevation to top,
climb avg gradient), lap metrics, NP/kJ/TSS, per-frame smooth marker interpolation, backing panels.
