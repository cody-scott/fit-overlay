# render-cli — agent guide

`fit-render`: FIT file + overlay spec + time slice → transparent overlay video.
It is a self-contained unit of the monorepo (own `pyproject.toml`, `uv.lock`,
Dockerfile, tests). The future API worker will run it **via its Docker image**, so
the CLI's machine interface is a public contract (see below).

## Commands (run from `render-cli/`)

```bash
uv sync                                   # install (Python 3.12)
uv run pytest                             # tests; -m "not ffmpeg" skips encoder tests
uv run ruff format . && uv run ruff check . && uv run mypy   # must all pass (mypy strict)
uv run fit-render --help
docker build -t fit-render .              # reference runtime
```

## Package layout and dependency direction

```
src/fit_render/
  domain/    Activity, Record, TimerEvent, Channel; Timeline(+Builder); Slice   ← depends on nothing
  ingest/    ActivityParser (ABC) → FitParser; ParserRegistry; load_activity    → domain
  units/     Quantity, UnitSystem, QuantityFormatter strategies, MISSING="--"  ← depends on nothing
  metrics/   Metric (ABC) → ChannelMetric / CompositeMetric(Smoothed, W/kg) / derived; registry → domain, units
  spec/      Pydantic OverlaySpec schema, YAML loader, templates, CLI overrides → units
  render/    Canvas (ABC) → PillowCanvas; Widget → TextWidget → Metric/Label; Overlay; OverlayBuilder → metrics, spec, units
  encode/    VideoEncoder (ABC) → FfmpegEncoder → IntraFrameEncoder → ProRes; WebM; PngSequence; find_ffmpeg → spec
  pipeline.py  OverlayPipeline → RenderPipeline / PreviewPipeline (the programmatic API)
  cli.py       Typer shell over pipeline.py — no business logic here
  templates/*.yaml, assets/fonts/
```

Keep units independent: lower layers never import higher ones (`domain` and `units`
import nothing from the package; nothing imports `cli`). Each subpackage exposes its
API through `__init__.py`; import from there, not from internal modules.

## Behaviour that must not regress

- **1-second grid.** Values update once per second. Second 0 = first record. Time is
  continuous through stops (wall clock); `total_time` includes stops, `moving_time` doesn't.
- **Stops.** Timer STOP events take effect the second *after* their timestamp (devices
  stamp them with the last record's time); START at its timestamp. While stopped with no
  data: speed/power/cadence = 0, distance/altitude hold, HR stays missing.
  Moving = timer running AND speed ≥ 0.5 m/s (no timer events → speed only).
  A **recording gap** (consecutive records > `pause_gap_s` = 10 s apart) is also a stop,
  even without timer events (TrainerRoad etc. just stop recording). Shorter gaps are not
  (smart recording logs every few seconds) — they stay `--` past the 2 s forward-fill.
- **Missing data** renders `--`. Gaps ≤ 2 s are forward-filled (recording jitter).
- **Slices** are whole seconds since activity start; warn > 30 s, error > 180 s.
- **Frame → second** uses exact `Fraction` math (`RenderPipeline.second_for_frame`) so
  29.97/59.94 fps never drift.
- **Frame de-duplication.** `Overlay.contents()` (cheap strings) decides whether a frame
  changed; only changed frames are drawn. `IntraFrameEncoder` encodes only unique frames
  then stream-copies them (concat demuxer) — ~25× faster for ProRes. Output must stay
  constant-frame-rate with the exact frame count.
- **Alpha** is straight (not premultiplied); background fully transparent; anti-aliased
  edges keep the text colour. Covered by `tests/test_render.py`.
- **Fonts** must have equal-width digits (tested) so values don't jiggle.
- Positions/sizes in specs are **fractions of the frame**, never pixels.

## Extending

- **Metric:** subclass `Metric` (or wrap one with `CompositeMetric`), register it in
  `metrics/registry.py::build_default_registry`, add a `Quantity`+formatter if new, test it.
- **Widget type:** add a `*WidgetSpec` to `spec/models.py` (with a `Tag` in `WidgetSpec`),
  a `Widget` subclass in `render/widgets.py`, and a factory entry in `OverlayBuilder`.
  `content()` must capture all visible state (it drives de-duplication).
- **Encoder:** subclass `VideoEncoder`/`FfmpegEncoder` (intra-only codecs: `IntraFrameEncoder`),
  add an `OutputFormat` value and an `ENCODERS` entry.
- **Parser (GPX/TCX):** subclass `ActivityParser`, register it in `ingest/__init__.py`.
- **Template:** drop a YAML file in `templates/`; `tests/test_spec.py` builds every template.

## CLI contract (consumed by the future API worker — change deliberately)

- `render ... --json` → one JSON object on stdout: `output, format, width, height, fps,
  start, end, frames, unique_frames, elapsed_s, warnings`.
- `inspect FILE --json` → summary incl. `duration_s`, `moving_time`, `channels_coverage_pct`, `has_gps`.
- `--progress json` → NDJSON on stderr: `{"event":"start","total"}`, `{"event":"progress","done","total","percent"}`, `{"event":"finish"}`.
- Exit codes: 0 ok, 1 `FitRenderError` (clean message on stderr, never a traceback), 2 usage.
- All user-caused errors raise a `FitRenderError` subclass (`errors.py`).

## Testing notes

- `tests/fitgen.py` writes deterministic synthetic FIT files with the Garmin SDK encoder
  (600 s ride, 60 s auto-pause at 200 s, HR dropout at 300 s, 5 % climb 400–500 s).
  Prefer extending `RideShape` over committing binaries.
- Real rides go in `tests/fixtures/*.fit` (auto-parametrised). Trim them first if they
  reveal a home location.
- `@pytest.mark.ffmpeg` tests run the bundled ffmpeg and verify codec, alpha, frame count.
