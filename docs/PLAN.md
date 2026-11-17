# fit-overlay plan

## Goal

Take a `.fit` file, let the user choose a slice, and export a transparent video
(text only) to overlay on their own ride footage. Cycling first.

## Decisions

| Topic | Decision |
|---|---|
| Users / hosting | Self-hosted on a home PC, not public, no auth. Nothing persisted between runs (for now). |
| Input | `.fit` only (GPX/TCX possible later via the parser registry). The app never takes the user's video. |
| Sync | User syncs the overlay in their editor; the app only renders. |
| Sport | Cycling. |
| Slice | Whole seconds, *time since activity start* (`H:MM:SS`). Warn > 30 s, max 3 min. |
| Time model | 1 Hz updates; wall-clock time continuous through stops. `total_time` vs `moving_time`. |
| Stops | Detected from the data: device timer events, plus speed < 0.5 m/s. |
| Metrics (v1) | power, 3 s power, W/kg, HR, speed, cadence, elevation, distance, gradient, total time, moving time, clock. |
| Smoothing | 3 s average for power by default; configurable per widget. |
| Missing data | `--` (gaps ≤ 2 s forward-filled). |
| Styling | Text only — no outline/shadow. One bundled monospace font family (Roboto Mono). |
| Layout | Templates + fractional anchor/offset/size per widget. Drag-and-drop later (UI). |
| Output | User choice: ProRes 4444 `.mov` (default), VP9 `.webm`, PNG sequence. Standard frame sizes + fps presets. |
| ffmpeg | Bundled via `imageio-ffmpeg` (also used in Docker); override with `FFMPEG_PATH`. |
| Deployment | Docker per unit, linked with compose. The API worker runs the `fit-render` image. |
| Repo | Monorepo; each unit is self-contained with its own `AGENTS.md`. |

## Phases

### Phase 1 — render CLI (`render-cli/`) ✅

- [x] M0 Scaffolding: uv project, ruff, mypy strict, pytest, Dockerfile, CI
- [x] M1 Ingest: FIT parser (Garmin SDK), timeline on 1 s grid, timer events, `inspect`
- [x] M2 Metrics: registry, raw/derived/smoothed metrics, units, formatting, `--`
- [x] M3 Spec: Pydantic schema, YAML loader, 4 templates (minimal, column, bottom-bar, vertical), overrides
- [x] M4 Renderer: Canvas/Pillow, widgets, layout anchors, `preview`
- [x] M5 Encoders + pipeline: ProRes 4444 (unique-frame fast path), WebM, PNG sequence, progress, JSON contract
- [x] M6 Docs: READMEs, AGENTS.md files, this plan
- [x] M6.2 Spec authoring guide for agents + JSON Schema (`render-cli/docs/spec/`, `fit-render schema`)
- [ ] `fit-render validate` with off-frame/overlap warnings (see `render-cli/PLAN.md` M6.2)
- [ ] Validate with real FIT files from the user's devices (`render-cli/tests/fixtures/`)
- [ ] Verify imports in Premiere Pro and Final Cut Pro on real footage

### Phase 2 — API + worker (`api/`)

- FastAPI service: upload FIT → `inspect` summary + downsampled series for charts; list templates/metrics.
- Preview endpoint (single PNG frame via `fit-render preview`).
- Render jobs: queue (Redis + Dramatiq/arq), worker invokes `fit-render` Docker image with
  `--json --progress json`, progress pushed to clients via SSE, download endpoint.
- Temp storage on a shared volume with cleanup (no persistence between sessions).
- `compose.yaml` with api, worker, redis.

### Phase 3 — Web UI (`web/`)

- React + TypeScript + Vite, TanStack Query, Zustand.
- Upload → activity summary → timeline chart with brush to select the slice (snap to laps).
- Template picker, metric/units/weight settings, export settings (size, fps, format).
- Preview pane (backend-rendered frame over checkerboard), job progress, downloads.
- nginx container serving the build and proxying `/api`.

### Phase 4 — Map start point

- MapLibre/Leaflet track map when GPS exists; click to set slice start; sync with chart brush.
- Tile provider decision (self-hosted or keyed provider; OSM tile policy disallows heavy use).

### Later

- Spec editor with drag-and-drop positioning; more fonts; text outline/shadow.
- Widgets: gauges, sparklines, minimap (separate overlay).
- Other sports, GPX/TCX parsers, imperial 12 h clock option, lap/segment-aware slices.

## Open questions

- Which editors are in daily use (confirms ProRes 4444 default vs WebM)?
- Real-device FIT quirks (smart recording intervals, developer fields) — pending fixture files.
