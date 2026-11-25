# Overlay spec reference (version 1)

Source of truth: `src/fit_render/spec/models.py` (Pydantic). Machine-readable form:
[`overlay-spec.schema.json`](overlay-spec.schema.json) (`fit-render schema`). Unknown keys are
rejected everywhere.

```yaml
version: 1                       # optional, must be 1
name: my-overlay                 # optional, default "custom"
description: One line.           # optional
units: metric                    # metric | imperial
rider: { weight_kg: 72 }         # optional
output: { size: 1080p, fps: "30", format: prores4444 }
style: { font: roboto-mono-bold, color: "#FFFFFF" }
widgets:                         # required, at least one, drawn in order
  - { type: metric, metric: power_3s, label: PWR, anchor: bottom-left, offset: [0.03, 0.04], size: 0.05 }
  - { type: label, text: "Hill repeat #3", anchor: top, offset: [0, 0.04], size: 0.04 }
```

## Top level

| Field | Type | Default | Notes |
|---|---|---|---|
| `version` | `1` | `1` | Only version 1 exists. |
| `name` | string | `custom` | Built-in templates: must equal the file name. |
| `description` | string | `""` | Shown by `fit-render templates list`. |
| `units` | `metric` \| `imperial` | `metric` | Imperial changes speed (mph), distance (mi), elevation (ft). Others unchanged. CLI `--units` overrides. |
| `rider.weight_kg` | number, 20 < x < 300 | `null` | Needed by `power_to_weight`. Falls back to the FIT user profile, then `--`. CLI `--weight` overrides. |
| `output` | object | see below | |
| `style` | object | see below | Defaults for every widget. |
| `widgets` | list (≥ 1) | — | Metric and label widgets. Later widgets draw on top. |

## `output`

| Field | Values | Default |
|---|---|---|
| `size` | `720p` 1280×720 · `1080p` 1920×1080 · `1440p` 2560×1440 · `2.7k` 2704×1520 · `4k` 3840×2160 · `vertical-720` 720×1280 · `vertical-1080` 1080×1920 · `vertical-4k` 2160×3840 · `square-1080` 1080×1080 · or `WIDTHxHEIGHT` (even numbers, 2–5 digits each) | `1080p` |
| `fps` | `"23.976"` `"24"` `"25"` `"29.97"` `"30"` `"50"` `"59.94"` `"60"` — quote it | `"30"` |
| `format` | `prores4444` (.mov; Premiere, Final Cut, Resolve) · `webm` (VP9 + alpha; small, limited editor support) · `png-seq` (directory of RGBA PNGs) | `prores4444` |

All three can be overridden on the command line (`--size`, `--fps`, `--format`; the format also
follows the `--out` suffix). Match `size` and `fps` to the footage.

## `style`

| Field | Values | Default |
|---|---|---|
| `font` | `roboto-mono`, `roboto-mono-bold` | `roboto-mono-bold` |
| `color` | `#RGB`, `#RRGGBB`, `#RRGGBBAA` (AA = opacity, `FF` opaque) | `#FFFFFF` |

## Widgets — common fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `metric` \| `label` | `metric` | |
| `anchor` | `top-left` `top` `top-right` `left` `center` `right` `bottom-left` `bottom` `bottom-right` | `top-left` | The frame point the widget is pinned to. It also sets text alignment. See `layout.md`. |
| `offset` | `[x, y]`, each 0–1 | `[0.03, 0.03]` | Inset from the anchored edge(s) as fractions of frame width / height. On a centred axis it shifts right / down. |
| `size` | 0 < x ≤ 0.5 | `0.05` | Font size as a fraction of frame **height**. The visible line is ≈ 1.32 × size. |
| `font` | font name | `style.font` | Per-widget override. |
| `color` | colour | `style.color` | Per-widget override. |

### `type: metric`

| Field | Type | Default | Notes |
|---|---|---|---|
| `metric` | metric key (below) | — required | |
| `label` | string | none | Drawn before the value with one space: `HR 165 bpm`. |
| `show_unit` | bool | `true` | `false` → `HR 165`. |
| `smoothing_s` | int 1–60 | none | Trailing mean over N seconds, ignoring missing samples. |

Displayed text = `[label] value [unit]`, joined with single spaces. Missing value → `--`
(still followed by the unit: `-- bpm`).

### `type: label`

| Field | Type | Notes |
|---|---|---|
| `text` | string, non-empty | Static text, one line. Use it for titles and captions. |

## Metrics

Values update once per second. "Worst case" is the longest realistic text with the unit, no label
— use it for spacing (see `layout.md`). Times are counted from the **activity** start, not the clip.

| Key | Shows | Metric / imperial | Needs channels | Worst case | Notes |
|---|---|---|---|---|---|
| `power` | Instant power | `W` | power | `1234 W` (6) | Jumpy. Prefer `power_3s`. |
| `power_3s` | 3 s average power | `W` | power | `1234 W` (6) | Default choice for power. |
| `power_to_weight` | Power ÷ weight | `W/kg`, 1 dp | power + rider weight | `12.3 W/kg` (9) | Instant power; add `smoothing_s: 3`. `--` without a weight. |
| `heart_rate` | Heart rate | `bpm` | heart_rate | `185 bpm` (7) | Stays `--` during stops with no data. |
| `speed` | Speed | `km/h` / `mph`, 1 dp | speed | `102.4 km/h` (10) · `63.6 mph` (8) | 0 while stopped. |
| `cadence` | Cadence | `rpm` | cadence | `120 rpm` (7) | |
| `elevation` | Altitude | `m` / `ft` | altitude | `2345 m` (6) · `12345 ft` (8) | Holds during stops. |
| `distance` | Distance so far | `km` / `mi`, 2 dp | distance | `123.45 km` (9) · `76.71 mi` (8) | Since activity start. |
| `gradient` | Road gradient | `%`, 1 dp | altitude + distance | `-12.5 %` (7) | Rise over the last ≥ 20 m (max 30 s back); `--` when slow/stopped. Use `smoothing_s: 5`. |
| `total_time` | Elapsed time incl. stops | `H:MM:SS`, no unit | — | `1:23:45` (7; 8 past 10 h) | |
| `moving_time` | Moving time | `H:MM:SS`, no unit | speed / timer | `1:23:45` (7) | Moving = timer running and speed ≥ 0.5 m/s. |
| `clock` | Local time of day | `HH:MM:SS` 24 h, no unit | timestamps | `14:05:09` (8) | Uses the device's UTC offset, else the machine's zone. |

`fit-render metrics` prints the live list. The JSON Schema enumerates the same keys.

## Validation errors

Bad specs fail with exit code 1 and a list of problems, one per field. Widget paths are
`widgets.<index>.<type>.<field>`:

```
error: my-overlay.yaml is invalid:
  - output.fps: Value error, Unsupported fps '29.9'; use one of 23.976, 24, 25, 29.97, 30, 50, 59.94, 60
  - widgets.0.metric.metric: Field required
  - widgets.1.metric.offset: Value error, offset values must be between 0 and 1
```

Unknown metric or font names are reported when the overlay is built (`preview`/`render`):
`Unknown metric 'hr'; available: cadence, clock, ...`.

## Not supported yet

Graphs/sparklines/elevation profile (M7–M8), outline and drop shadow (M9), min/max/avg
aggregates (M10), backgrounds/panels, zones, extra fonts, multi-line text. See `../../PLAN.md`.
Don't invent fields for these — they will be rejected.
