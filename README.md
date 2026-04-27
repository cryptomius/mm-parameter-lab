# Market-Maker Simulator & Parameter Lab

> A discrete-time Avellaneda-Stoikov market-making simulator with a stress
> scenario library, intervention modules, and a reproducible findings
> pipeline. The centrepiece deliverable is the **Findings Document**
> (`docs/findings.md`); the simulator and live UI exist to make the
> findings reproducible.

## What's in here

- **`backend/mm_sim/`** — the simulation engine: market processes (GBM,
  OU, jump-diffusion), L2 order book, noise + informed traders, the AS
  quoter (infinite-horizon variant), five toggleable interventions,
  online metrics, and parquet results writer.
- **`backend/runner/`** — headless CLI that consumes
  `backend/experiments.yaml` and runs experiments in series or with
  multiprocessing.
- **`backend/server/`** — FastAPI + websocket server for the live UI.
- **`frontend/`** — Vite + React + TypeScript single-page app: order
  book ladder, inventory and PnL charts, live parameter retuning,
  intervention toggles, and scenario injection.
- **`notebooks/`** — Python analysis scripts (one per finding) that
  read parquet results and emit every chart referenced in the findings
  document.
- **`docs/`** — `findings.md` (the analytical write-up),
  `math_appendix.md`, and `figures/` (PNGs produced by the notebooks).
- **`scripts/`** — one-line build steps:
  `run_all_experiments.sh`, `render_all_figures.sh`, `build_findings_pdf.sh`.

## Run it from scratch

```bash
# 1. install
uv sync --extra dev --extra notebooks
pnpm --dir frontend install

# 2. run the experiments (~5hr single-thread; ~1hr with WORKERS=8)
WORKERS=8 bash scripts/run_all_experiments.sh

# 3. render every figure in the findings doc
bash scripts/render_all_figures.sh

# 4. build the findings PDF (requires pandoc + xelatex)
bash scripts/build_findings_pdf.sh
```

## Run a single experiment

```bash
uv run python -m runner.cli list                              # show all experiments
uv run python -m runner.cli run "f1_gamma_sweep_low_vol"      # one
uv run python -m runner.cli run "f1_*" --workers 4            # all of finding 1
uv run python -m runner.cli run "baseline_calm" --dry-run     # show the resolved configs without running
```

## Run the live UI

Two terminals:

```bash
# backend
uv run uvicorn server.app:app --reload --app-dir backend

# frontend
pnpm --dir frontend dev
```

Then open <http://localhost:5173>. Pick an experiment from the dropdown,
press Start, and use the right-hand panel to retune parameters or
inject scenarios mid-simulation.

## Run tests

```bash
uv run pytest
```

## What's modelled vs what isn't

This is a **teaching/demonstration tool**, not a production system. See
`docs/findings.md` §9 for the explicit list of what's deliberately out
of scope (latency modelling, real fee schedules, multi-venue, real
microstructure, ML, real exchange connectivity).

## License

MIT.
