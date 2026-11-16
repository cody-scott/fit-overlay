# fit-overlay

Generate transparent data overlays (power, heart rate, speed, W/kg, …) from `.fit`
files, for compositing onto ride video in Premiere Pro, Final Cut Pro or Resolve.

| Unit | Status |
|---|---|
| [`render-cli/`](render-cli/README.md) | `fit-render` CLI — FIT + spec + slice → transparent ProRes/WebM/PNG overlay |
| `api/` | planned — FastAPI backend + render worker |
| `web/` | planned — React UI |

Quick start:

```bash
cd render-cli && uv sync
uv run fit-render inspect ride.fit
uv run fit-render render ride.fit -t minimal --start 12:30 --end 13:00 -o clip.mov
```

See [`docs/PLAN.md`](docs/PLAN.md) for decisions and roadmap, and `AGENTS.md` for
contributor/agent guidance.
