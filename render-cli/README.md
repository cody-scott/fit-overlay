# fit-render

Command-line renderer that turns a slice of a `.fit` activity into a **transparent
overlay video** (text only, alpha everywhere else) for compositing onto ride footage
in Premiere Pro, Final Cut Pro, DaVinci Resolve, etc.

## Install / run

```bash
cd render-cli
uv sync                      # Python 3.12; ffmpeg ships with the imageio-ffmpeg wheel
uv run fit-render --help
```

Or with Docker:

```bash
docker build -t fit-render render-cli
docker run --rm -v "$PWD:/work" fit-render render ride.fit --start 12:30 --end 13:00 -o clip.mov
```

## Usage

```bash
fit-render inspect ride.fit                       # duration, data present, stops
fit-render templates list                         # built-in layouts
fit-render metrics                                # metric keys, fonts, sizes, fps

# Check a layout on one frame (PNG), then render the slice
fit-render preview ride.fit -t column --at 12:45 -o frame.png
fit-render render  ride.fit -t column --start 12:30 --end 13:00 -o clip.mov

# Overrides: size / fps / format / units / rider weight
fit-render render ride.fit -t vertical --start 1:02:00 --end 1:02:30 \
    -o clip.webm --fps 59.94 --units imperial --weight 72
```

Times are **time since the activity started** (`H:MM:SS`, `MM:SS` or seconds) and
include stops. Slices over 30 s warn; the maximum is 3 min.

| Format (`--format`) | Output | Notes |
|---|---|---|
| `prores4444` (default) | `.mov` | ProRes 4444 + alpha. Works in every major editor. Large (~170 MB per 30 s at 1080p). |
| `webm` | `.webm` | VP9 + alpha. Tiny files; limited editor support. |
| `png-seq` | directory | Numbered RGBA PNGs. Universal fallback. |

The format defaults to the `--out` suffix when `--format` is omitted.

## Overlay specs

Start from a template and customise it:

```bash
fit-render templates show minimal > my-overlay.yaml
fit-render preview ride.fit --spec my-overlay.yaml --at 5:00
```

```yaml
version: 1
units: metric                 # or imperial
rider: { weight_kg: 72 }      # for W/kg (falls back to the FIT user profile)
output: { size: 1080p, fps: "30", format: prores4444 }
style: { font: roboto-mono-bold, color: "#FFFFFF" }
widgets:
  - { metric: power_3s, label: PWR, anchor: bottom-left, offset: [0.03, 0.05], size: 0.06 }
  - { metric: gradient, smoothing_s: 5, anchor: bottom-right, offset: [0.03, 0.05], size: 0.05 }
  - { type: label, text: "Hill repeat #3", anchor: top, offset: [0, 0.04], size: 0.04 }
```

- `anchor`: `top-left`, `top`, `top-right`, `left`, `center`, `right`, `bottom-left`, `bottom`, `bottom-right`
- `offset`: inset from the anchored edge(s) as fractions of width/height
- `size`: text height as a fraction of frame height
- `smoothing_s`: trailing rolling average; `show_unit: false` hides the unit
- Sizes: `720p 1080p 1440p 2.7k 4k vertical-720 vertical-1080 vertical-4k square-1080` or `WIDTHxHEIGHT`
- FPS: `23.976 24 25 29.97 30 50 59.94 60`

Metrics: `power power_3s power_to_weight heart_rate speed cadence elevation distance
gradient total_time moving_time clock`. Missing data renders as `--`.

## Machine interface (for the API worker)

- `--json`: `render` prints one JSON result object on stdout; `inspect --json` prints a summary.
- `--progress json`: newline-delimited `{"event": "start"|"progress"|"finish", ...}` on stderr.
- Exit code `0` success, `1` user/data error (message on stderr), `2` usage error.

## Development

```bash
uv run pytest                 # all tests (ffmpeg tests use the bundled binary)
uv run pytest -m "not ffmpeg" # skip encoder tests
uv run ruff format . && uv run ruff check . && uv run mypy
uv run python tests/fitgen.py /tmp/ride.fit   # synthetic ride for manual testing
```

Drop real `.fit` files into `tests/fixtures/` and they are parsed by the test suite.

Fonts: Roboto Mono, SIL Open Font License 1.1 (`src/fit_render/assets/fonts/OFL.txt`).
