# fit-overlay — agent guide

Generate **transparent data overlays** (power, HR, speed, W/kg, …) from `.fit` files.
The user picks a slice of a ride and gets an alpha video containing only text, which
they drop onto their footage and sync themselves in Premiere / Final Cut / Resolve.
The app never ingests the user's video. Self-hosted on a home PC; not public; no auth.

See `docs/PLAN.md` for decisions and the roadmap.

## Monorepo layout

Each top-level directory is an **independent unit** with its own dependencies,
tooling, tests, Dockerfile and `AGENTS.md`. Units never import each other's code;
they integrate through explicit contracts (CLI flags/JSON, HTTP).

| Path | Status | What |
|---|---|---|
| `render-cli/` | built (phase 1) | `fit-render` Python CLI: FIT + spec + slice → overlay video. See `render-cli/AGENTS.md`. |
| `api/` | planned (phase 2) | FastAPI backend + worker; runs renders via the `fit-render` Docker image. |
| `web/` | planned (phase 3) | React + TypeScript (Vite) UI: upload, chart/brush slice selection, preview, export. |
| `docs/` | | Plan and decisions. |
| `compose.yaml` | planned | Links `web` + `api` (+ worker, Redis) for deployment. |

Target architecture:

```
web (nginx + React) ──/api──▶ api (FastAPI) ──queue (Redis)──▶ worker ──docker run──▶ fit-render
                                    └──────────── shared /data volume ────────────┘
```

## Conventions

- Python units: Python 3.12, `uv` (commit `uv.lock`), `ruff` (format + lint), `mypy --strict`,
  `pytest`. Run tooling from inside the unit's directory.
- Design: small cohesive subpackages, ABCs + composition (Strategy, Registry, Composite,
  Bridge, Template Method). Business logic stays out of CLI/HTTP layers.
- User-facing errors are typed exceptions with clean messages — no tracebacks for bad input.
- Don't commit render outputs (`*.mov`, `*.webm`, `out/`) or large media. FIT files can
  reveal home locations; trim before committing as fixtures.
- CI: `.github/workflows/<unit>.yml`, path-filtered per unit.
- Work on feature branches off `main`.
