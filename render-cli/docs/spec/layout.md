# Layout geometry

Everything is a fraction of the frame, so one spec works at any resolution **with the same aspect
ratio**. Notation: frame `W × H` pixels, widget `size = s`, `offset = [ox, oy]`.

Source: `src/fit_render/render/layout.py` (`Placement.resolve`) and `render/fonts.py`.

## Anchors

The anchor picks a reference point on the frame **and** how the text hangs from it.

```
 top-left ─────────── top ─────────── top-right
    │                                      │
   left ────────────  center  ──────────  right
    │                                      │
 bottom-left ──────── bottom ──────── bottom-right
```

| Anchor | Reference x | Text is… | Reference y | Line is… |
|---|---|---|---|---|
| `*-left`, `left` | `ox·W` | left-aligned (grows right) | | |
| `top`, `center`, `bottom` | `W/2 + ox·W` | centred | | |
| `*-right`, `right` | `W − ox·W` | right-aligned (grows left) | | |
| `top-*`, `top` | | | `oy·H` | hanging below (y = top of the line box) |
| `left`, `center`, `right` | | | `H/2 + oy·H` | centred on y |
| `bottom-*`, `bottom` | | | `H − oy·H` | sitting above (y = bottom of the line box) |

- Offsets are **insets** from the anchored edge, always `0 ≤ o ≤ 1`. On a centred axis they can
  only push right/down. To place something left of centre, use a `*-left` anchor with `ox < 0.5`.
- The line box comes from font metrics, not from the characters drawn, so text never shifts
  vertically when digits change.
- Right-aligned values grow leftwards. Put right-hand columns on `*-right` anchors so the units
  line up and nothing runs off the frame.

## Font metrics (Roboto Mono, both weights)

All in **em**, where 1 em = `s·H` pixels.

| Quantity | em | As a fraction of frame height |
|---|---|---|
| Line box height (ascent 1.048 + descent 0.271) | **1.32** | `1.32·s` |
| Digit / capital height | 0.72 | `0.72·s` |
| Empty space above capitals inside the line box | 0.33 | `0.33·s` |
| Baseline above the bottom of the line box | 0.27 | `0.27·s` |
| Advance width of **every** character (monospaced, incl. space) | **0.60** | — |

So the *visible* gap to the frame edge is larger than the offset: with `top-*`, digits start
`oy + 0.33·s` from the top; with `bottom-*`, they sit `oy + 0.27·s` above the bottom.

## Text width

```
width (fraction of W) = chars × 0.6 × s × H / W  = chars × s × k
```

| Aspect | Sizes | k |
|---|---|---|
| 16:9 | 720p, 1080p, 1440p, 4k, 2.7k (≈) | **0.3375** |
| 1:1 | square-1080 | 0.6 |
| 9:16 | vertical-720/1080/4k | **1.0667** |

`chars` counts the label, the spaces, the value and the unit: `HR 185 bpm` = 10. Use the
**worst-case** widths from the metric table in `reference.md`, not the value in one preview.

Examples (16:9): `PWR 1234 W` at `s = 0.04` → 10 × 0.04 × 0.3375 = **0.135 W**.
On 9:16 the same text is 0.427 W — phones need small sizes and short labels.

## Stacking rows (same anchor, same column)

Rows don't overlap when the distance between their reference lines is at least the line box:

```
pitch ≥ 1.32 × s            (same size; 1.4–1.5 × s looks comfortable)
```

- `top-*`: next `oy` = previous `oy` + 1.32 × previous `s` + gap.
- `bottom-*` (build upwards): next `oy` = previous `oy` + 1.32 × previous `s` + gap — "previous"
  being the row below, i.e. the one you already placed.
- `left`/`center`/`right`: centre-to-centre ≥ 0.66 × (s₁ + s₂) + gap.

Worked example (`examples/corner-stack.yaml`, bottom-left, built upward):

| Row | s | oy | line box spans (from bottom) |
|---|---|---|---|
| `power_3s` | 0.080 | 0.040 | 0.040 – 0.146 |
| `W/KG` | 0.035 | 0.160 | 0.160 – 0.206 |
| `HR` | 0.035 | 0.215 | 0.215 – 0.261 |
| `CAD` | 0.035 | 0.270 | 0.270 – 0.316 |

(The built-in `minimal` template lets rows touch slightly: 0.04 + 1.32 × 0.075 = 0.139 > 0.135.
It's fine because digits have no descenders, but leave a gap in new specs.)

## Side by side (same row)

```
next ox ≥ previous ox + worst-case width + gap        (gap ≥ one character = 0.6·s·H/W)
```

`bottom-bar` uses steps of 0.16 W at `s = 0.045` (one char = 0.0152 W): the widest value,
`12.3 W/kg` (9 chars), takes 0.137 W, leaving a gap of about 1.5 characters.

For two columns, anchor the left one `*-left` and the right one `*-right`; check that
`ox_left + width_left + gap ≤ 1 − ox_right − width_right`.

## Sizes and margins (rules of thumb)

| Role | `size` (16:9) | `size` (9:16) |
|---|---|---|
| Hero value (one big number) | 0.06 – 0.08 | 0.04 – 0.05 |
| Normal value | 0.035 – 0.05 | 0.025 – 0.04 |
| Caption / small label | 0.015 – 0.025 | 0.014 – 0.02 |

- Keep `offset ≥ 0.03` from every edge (0.05 if the video may be cropped or shown on a TV).
- Vertical (Reels / Shorts / TikTok): app UI covers roughly the bottom 15 % and a strip on the
  right. Keep values above `oy ≈ 0.15` and away from the right edge, or check with the user.
- Group related metrics in one or two corners rather than spreading them around the frame.
- Use `#RRGGBBAA` with lower opacity (e.g. `#FFFFFFB3`) for captions and secondary values.

## Changing frame size

- **Same aspect** (1080p → 4k): identical layout, nothing to change.
- **Different aspect** (`--size vertical-1080` on a 16:9 template): heights scale with H, but
  widths are multiplied by `H / W`, so rows that fitted side by side overlap or run off the frame.
  Write a separate spec per aspect ratio (as `vertical.yaml` does).
