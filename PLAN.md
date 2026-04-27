# Market Maker Simulator & Parameter Lab — Implementation Plan

**Status:** v1, pre-implementation. Five design defaults locked in (see Appendix A).
**Scope budget:** ~2 weeks part-time.
**Centrepiece deliverable:** the Findings Document. Everything else exists to make it reproducible.

---

## 0. Locked design defaults

| # | Decision |
|---|---|
| D1 | Finding 4 uses Monte Carlo: 20 seeds per (γ, σ-mult) cell, report mean PnL with 5/95 percentile shading. |
| D2 | AS quoter uses infinite-horizon variant: replace `(T−t)` with constant `τ` (default 300s lookback). Original formula in math appendix. |
| D3 | Informed traders observe `true_price(t+Δ) + noise` with Δ ∈ [1s, 30s], calibrated to ~55–60% directional hit rate. Same arrival distribution as noise traders — only direction is biased. |
| D4 | Quoter σ is EWMA realised vol with configurable half-life. UI toggle for "cheat mode" (true σ). Cheat-vs-rolling becomes a sub-finding inside Finding 1. |
| D5 | 20 individual counterparties with stable IDs. 4 informed (varying signal strength), 16 noise. Adverse-selection-penalty intervention learns toxicity per ID via rolling estimator. |

Plus two smaller defaults: scenarios use 30min warm-up / event / 30min recover window; runtime budget assumes ~30s wall-clock per simulated hour at 100ms quote refresh.

---

## 1. Findings Document Outline

The Findings doc is the artefact. Built in `docs/findings.md` → exported to PDF via Pandoc at the end. Every chart referenced by filename, every chart reproducible from a saved experiment config.

### §1 Executive Summary (½ page)

- One-paragraph project pitch: "Built an interactive Avellaneda-Stoikov market-making simulator and ran controlled experiments on inventory aversion, adverse selection, and stress-scenario interventions. This document reports what I observed."
- 5 bullet headline findings (filled in after experiments run — placeholder examples):
  - Doubling γ in low-vol regimes cut peak inventory by ~60% but only cost ~15% of gross spread capture.
  - In high-vol regimes the same γ doubling cost ~40% of spread capture — γ does not transfer across regimes.
  - With 20% informed flow, naïve AS bled ~X bps/hr to adverse selection; the per-counterparty penalty intervention recovered ~Y of it.
  - News-detector kill switch helped jump scenarios but *hurt* PnL in liquidity-withdrawal scenarios by suppressing quotes during recoverable conditions.
  - The single biggest observed PnL determinant was not γ — it was σ-estimation half-life. Stale σ in fast regimes was catastrophic.
- One-line "what surprised me most": placeholder, filled after analysis.

### §2 The Setup (½ page)

- Architecture diagram (text or mermaid): generator → L2 book → quoter ⇄ counterparties; metrics tap; results writer.
- What is modelled: synthetic mid via GBM/OU/jump-diffusion; L2 book with passive limit + market arrivals; AS quoter with toggleable interventions; per-counterparty fill attribution.
- What is *not* modelled: latency (mostly), real fee schedules, real exchange queue dynamics, multi-venue, real microstructure (no MBO, no iceberg detection, no auction phases), no ML.
- Limitations honestly listed before any results are shown.

### §3 Baseline Behaviour (1 page)

Establishes "what normal looks like" for the reader before stress is introduced.

- Setup: GBM, σ_true=0.01/√s, 4hr session, default AS params (γ=0.1, k=1.5, τ=300, EWMA half-life 60s), no informed flow, no interventions.
- Charts:
  - `baseline_price_and_quotes.png` — mid + bid/ask quotes overlay, 30min window
  - `baseline_inventory.png` — inventory over time with limit bands
  - `baseline_pnl_decomp.png` — stacked area, spread PnL vs inventory PnL vs fees
  - `baseline_fill_distribution.png` — histogram of fill sizes by side
- Headline numbers reported in a small table: total PnL, spread capture rate (fills per quote), max |inventory|, time-at-limit %, quote uptime %.

### §4 Finding 1 — The Inventory Aversion Trade-off (1 page)

Question: how does γ affect PnL and inventory excursions?

- Experiment `f1_gamma_sweep_low_vol`: same seed, γ ∈ {0.01, 0.1, 0.5, 1.0, 5.0}.
- Experiment `f1_gamma_sweep_high_vol`: same as above with σ_true × 3.
- Experiment `f1_sigma_estimation`: γ=0.1 fixed, sweep EWMA half-life ∈ {5s, 30s, 60s, 300s, ∞=cheat}. (Sub-finding from D4.)
- Charts:
  - `f1_pnl_vs_gamma.png` — line plot, two regimes overlaid
  - `f1_inventory_envelope.png` — fan chart of |inventory| percentiles per γ
  - `f1_spread_width_vs_gamma.png` — average half-spread per γ
  - `f1_sigma_halflife_pnl.png` — sub-finding: PnL vs EWMA half-life, separated by regime
- Claim template: "At γ=0.1 in low-vol the MM captured X bps/hr with peak |inv|=Y. Doubling γ to 0.2 reduced peak |inv| by Z% and reduced PnL by W%. In high-vol the same doubling reduced PnL by W'%, demonstrating γ does not transfer across regimes."
- Discussion: lays groundwork for Finding 4 (parameter interactions).

### §5 Finding 2 — Adverse Selection and the Cost of Naïve Quoting (1.5 pages)

Question: what does adverse selection actually look like, and what does it cost?

- Experiment `f2_informed_fraction_sweep`: GBM market, informed-trader fill share ∈ {0%, 10%, 20%, 30%}, no interventions.
- Experiment `f2_penalty_intervention`: 20% informed, compare {no intervention} vs {per-counterparty penalty} vs {global widening}.
- Charts:
  - `f2_post_fill_drift_histograms.png` — distribution of mid move 1s/10s/60s post-fill, separated by side. With informed flow, the histogram skews against the MM (price moves up after MM sells, down after MM buys).
  - `f2_pnl_decomp_by_informed_share.png` — stacked bars showing inventory PnL eating spread capture as informed share rises.
  - `f2_intervention_recovery.png` — PnL bars for {no int, per-counterparty, global widening} at 20% informed flow.
  - `f2_counterparty_toxicity_learning.png` — per-counterparty estimated toxicity over time, showing penalty intervention separating informed from noise IDs.
- Claim template: "Without informed flow, post-fill drift was symmetric (mean ≈ 0). At 20% informed share, post-fill drift was −X bps for MM bids and +X bps for MM asks at 10s horizon, eroding gross spread capture from Y bps/hr to Z bps/hr — a W% drop. Per-counterparty penalty recovered V% of the lost PnL; global widening only recovered U%."
- Discussion: this is the silent killer. Spread capture in isolation is a vanity metric; PnL net of post-fill drift is the only honest scoreboard.

### §6 Finding 3 — Stress Scenario Responses (2 pages, ~½ page each)

For each of: rapid sell-off, news spike, liquidity withdrawal, toxic-flow burst.

For each scenario, run 4 variants on the same seed: {all interventions OFF}, {adaptive spread only}, {kill switch only}, {all interventions ON}.

- Experiments: `f3_selloff_*`, `f3_newsspike_*`, `f3_liqwithdraw_*`, `f3_toxicburst_*` (16 runs total).
- Charts (one of each per scenario):
  - `f3_<scenario>_pnl_during_event.png` — PnL trajectory across 4 variants, vertical line at event
  - `f3_<scenario>_inventory_during_event.png` — inventory across 4 variants
  - Single summary chart: `f3_intervention_effectiveness_grid.png` — bar chart, scenarios on x-axis, interventions as colour groups, y = ΔPnL vs no-intervention baseline.
- **Required honest finding:** at least one cell in the grid must show an intervention HURTING. Anticipated candidates:
  - Kill switch in liquidity-withdrawal: pulling quotes during a benign liquidity dip means the MM sits flat and earns nothing.
  - Adaptive spread in news spike: widening reactively after the spike means we miss the recovery rebound flow.
  - Per-counterparty penalty in toxic burst: rolling estimator hasn't seen the toxic IDs enough to flag them in time.
- Claim template: "In sell-off, kill switch reduced peak |inventory| by X% and improved PnL by Y bps. Same kill switch in liquidity-withdrawal reduced PnL by Z bps because no toxic flow ever materialised — the MM simply stopped earning the spread."

### §7 Finding 4 — Parameter Interaction Effects (1 page)

Question: do parameters interact, or can they be tuned independently?

- Experiment `f4_gamma_vol_grid`: 5×5 grid, γ ∈ {0.01, 0.1, 0.5, 1.0, 5.0} × σ-mult ∈ {0.5, 1, 2, 4, 8}, **20 seeds per cell** (D1).
- Charts:
  - `f4_pnl_heatmap.png` — mean total PnL across grid, with optimal-γ trace overlaid per σ column
  - `f4_pnl_heatmap_5pct.png`, `f4_pnl_heatmap_95pct.png` — percentile slices to show variance, demonstrating which cells are "really" different vs noise
  - `f4_optimal_gamma_vs_vol.png` — line plot extracted from grid: argmax γ per σ regime, with confidence band
- Claim template: "Optimal γ shifted from X at σ=0.5σ_baseline to Y at σ=4σ_baseline — a Wx change. The fixed-parameter MM operating at the low-vol optimum lost Z% of available PnL when vol shifted regimes. Implication: parameter scheduling is not optional."

### §8 What I'd Build Next (½ page)

- Adaptive γ scheduler: γ(t) = f(realised_vol(t)) — closing the loop on Finding 4.
- News detector with pre-emptive widening (vs reactive in current build).
- Multi-venue inventory netting with venue-specific σ and k.
- Counterparty-level adverse-selection scoring with decay and confidence weighting.
- Real exchange connectivity in shadow mode (paper-quoting against live BTCUSDT).

### §9 What This Project Is Not (½ page)

Honest framing: teaching tool, not production. What's missing: latency modelling beyond a single quote-refresh tick; real fee schedules and rebates; real exchange queue priority; ML-based informed-trader detection; auction phases; iceberg/hidden orders; multi-asset; cross-venue; real risk system. Why I built it anyway: parameter intuition, microstructure reasoning, the ability to defend specific numbers in a discussion — these don't come from reading the AS paper.

### Appendix A — Math reference

(Full content in §5 of this plan; copied into the findings doc as appendix.)

### Appendix B — Experiment manifest

(Pulled from §2 of this plan; included in the doc so reviewers can re-run anything.)

---

## 2. Experiment Manifest

Every experiment listed. Every cell in this table corresponds to one row in `experiments.yaml`, consumed by the headless runner.

### Baseline (§3)

```
experiment_id: baseline_calm
finding: 0
seed: 42
market_process: GBM, σ_true=0.01/√s, drift=0
duration: 4hr
events: none
quoter: AS, γ=0.1, τ=300, k=1.5, ewma_halflife=60s
interventions: none
counterparties: 16 noise + 0 informed
runs: 1
expected_runtime: ~2min
output_path: results/baseline_calm/
notebook: notebooks/03_baseline.ipynb
charts_produced: baseline_price_and_quotes.png, baseline_inventory.png, baseline_pnl_decomp.png, baseline_fill_distribution.png
```

### Finding 1 — Inventory Aversion (§4)

```
experiment_id: f1_gamma_sweep_low_vol
finding: 1
seed: 42
market_process: GBM, σ_true=0.01/√s
duration: 4hr
events: none
quoter: AS, γ ∈ {0.01, 0.1, 0.5, 1.0, 5.0}, τ=300, k=1.5, ewma_halflife=60s
interventions: none
counterparties: 16 noise
runs: 5
expected_runtime: ~10min
output_path: results/f1/gamma_sweep_low_vol/
notebook: notebooks/04_finding1.ipynb
charts_produced: f1_pnl_vs_gamma.png (low-vol series), f1_inventory_envelope.png (low-vol)

experiment_id: f1_gamma_sweep_high_vol
finding: 1
seed: 42
market_process: GBM, σ_true=0.03/√s   # 3x baseline
duration: 4hr
events: none
quoter: AS, γ ∈ {0.01, 0.1, 0.5, 1.0, 5.0}, τ=300, k=1.5, ewma_halflife=60s
interventions: none
counterparties: 16 noise
runs: 5
expected_runtime: ~10min
output_path: results/f1/gamma_sweep_high_vol/
notebook: notebooks/04_finding1.ipynb
charts_produced: f1_pnl_vs_gamma.png (high-vol series), f1_inventory_envelope.png (high-vol), f1_spread_width_vs_gamma.png

experiment_id: f1_sigma_estimation
finding: 1
seed: 42
market_process: GBM, σ_true=0.01 (low-vol session) and σ_true=0.03 (high-vol session) — two passes
duration: 4hr each
events: none
quoter: AS, γ=0.1, τ=300, k=1.5, ewma_halflife ∈ {5s, 30s, 60s, 300s, "cheat"}
interventions: none
counterparties: 16 noise
runs: 10 (5 halflives × 2 regimes)
expected_runtime: ~20min
output_path: results/f1/sigma_estimation/
notebook: notebooks/04_finding1.ipynb
charts_produced: f1_sigma_halflife_pnl.png
```

### Finding 2 — Adverse Selection (§5)

```
experiment_id: f2_informed_fraction_sweep
finding: 2
seed: 42
market_process: GBM, σ_true=0.01/√s
duration: 4hr
events: none
quoter: AS default
interventions: none
counterparties: 16 noise + N informed with Δ uniform in [1s, 30s], hit rate calibrated 55-60%
informed_fill_share_target: ∈ {0%, 10%, 20%, 30%}
runs: 4
expected_runtime: ~8min
output_path: results/f2/informed_fraction_sweep/
notebook: notebooks/05_finding2.ipynb
charts_produced: f2_post_fill_drift_histograms.png, f2_pnl_decomp_by_informed_share.png

experiment_id: f2_penalty_intervention
finding: 2
seed: 42
market_process: GBM, σ_true=0.01/√s
duration: 4hr
events: none
quoter: AS default
interventions: ∈ {none, per_counterparty_penalty, global_widening}
counterparties: 16 noise + 4 informed (informed_fill_share ≈ 20%)
runs: 3
expected_runtime: ~6min
output_path: results/f2/penalty_intervention/
notebook: notebooks/05_finding2.ipynb
charts_produced: f2_intervention_recovery.png, f2_counterparty_toxicity_learning.png
```

### Finding 3 — Stress Scenarios (§6)

For each scenario: 4 intervention variants. 4 scenarios × 4 variants = 16 runs.

```
experiment_id: f3_<scenario>_<variant>
finding: 3
seed: 42  (same across all f3 runs to isolate intervention effects)
market_process: GBM warm-up 30min → event at t=30min → recovery 30min
duration: 1hr
scenario ∈ {selloff, newsspike, liqwithdraw, toxicburst}
quoter: AS default
interventions ∈ {none, adaptive_spread_only, kill_switch_only, all_on}
counterparties: 16 noise + 4 informed (toxicburst makes informed fire concentrated)
runs: 16
expected_runtime: ~16min
output_path: results/f3/<scenario>/<variant>/
notebook: notebooks/06_finding3.ipynb
charts_produced: f3_<scenario>_pnl_during_event.png, f3_<scenario>_inventory_during_event.png; final aggregate f3_intervention_effectiveness_grid.png
```

### Finding 4 — Parameter Interactions (§7)

```
experiment_id: f4_gamma_vol_grid
finding: 4
seeds: 20 (range 1000-1019)
market_process: GBM, σ_true = baseline × σ_mult
duration: 4hr
events: none
quoter: AS, γ ∈ {0.01, 0.1, 0.5, 1.0, 5.0}, ewma_halflife=60s
σ_mult ∈ {0.5, 1, 2, 4, 8}
interventions: none
counterparties: 16 noise
runs: 5 × 5 × 20 = 500
expected_runtime: ~4hr (run overnight)
output_path: results/f4/gamma_vol_grid/
notebook: notebooks/07_finding4.ipynb
charts_produced: f4_pnl_heatmap.png, f4_pnl_heatmap_5pct.png, f4_pnl_heatmap_95pct.png, f4_optimal_gamma_vs_vol.png
```

### Total expected runtime budget

~5hr wall clock if Finding 4 runs single-threaded. With multiprocessing across 8 cores: ~1hr. All other findings < 1hr combined. Comfortably re-runnable in an evening.

---

## 3. File Structure

```
market-maker-visualiser/
├── README.md                         # one-page project pitch + how to run
├── PLAN.md                           # this document
├── pyproject.toml                    # uv-managed
├── uv.lock
├── .python-version                   # 3.12
├── .gitignore
│
├── docs/
│   ├── findings.md                   # the centrepiece document
│   ├── findings.pdf                  # exported via pandoc
│   ├── math_appendix.md              # AS derivation in plain English
│   ├── figures/                      # all PNGs referenced by findings.md
│   └── demo.gif                      # 3-min screen capture for README
│
├── backend/                          # Python — sim engine, runner, server
│   ├── mm_sim/
│   │   ├── __init__.py
│   │   ├── types.py                  # Pydantic models for all events/state
│   │   ├── rng.py                    # seedable RNG factory
│   │   ├── market/
│   │   │   ├── __init__.py
│   │   │   ├── processes.py          # GBM, OU, jump-diffusion mid generators
│   │   │   ├── book.py               # L2 order book
│   │   │   └── matching.py           # match logic, fill events
│   │   ├── traders/
│   │   │   ├── __init__.py
│   │   │   ├── noise.py              # Poisson limit + market orders
│   │   │   ├── informed.py           # forward-looking signal traders (D3)
│   │   │   └── counterparty.py       # ID assignment (D5)
│   │   ├── quoter/
│   │   │   ├── __init__.py
│   │   │   ├── avellaneda_stoikov.py # AS quoter, infinite-horizon variant (D2)
│   │   │   ├── vol_estimator.py      # EWMA realised vol (D4)
│   │   │   └── interventions.py      # adaptive_spread, kill_switch, hedge,
│   │   │                             # news_detector, per_counterparty_penalty
│   │   ├── scenarios/
│   │   │   ├── __init__.py
│   │   │   ├── library.py            # selloff, newsspike, liqwithdraw, etc.
│   │   │   └── timeline.py           # event scheduling
│   │   ├── metrics/
│   │   │   ├── __init__.py
│   │   │   ├── pnl.py                # spread, inventory, fees decomposition
│   │   │   ├── adverse_selection.py  # post-fill drift tracker
│   │   │   ├── inventory.py          # peak, time-at-limit
│   │   │   └── per_counterparty.py   # per-ID toxicity rolling estimate
│   │   ├── engine.py                 # event loop driving generator → book → quoter → metrics
│   │   ├── results.py                # parquet/jsonl writer
│   │   └── logging_config.py         # structured logs — feels like an ops tool
│   │
│   ├── runner/
│   │   ├── __init__.py
│   │   ├── cli.py                    # `python -m runner run <experiment_id>`
│   │   ├── manifest.py               # loads experiments.yaml
│   │   └── batch.py                  # parallel multiprocessing batch runner
│   │
│   ├── server/
│   │   ├── __init__.py
│   │   ├── app.py                    # FastAPI app
│   │   ├── ws.py                     # websocket state streamer
│   │   ├── rest.py                   # REST control endpoints
│   │   └── session.py                # in-memory live sim handle
│   │
│   ├── experiments.yaml              # the manifest from §2 in machine-readable form
│   └── tests/
│       ├── test_book.py
│       ├── test_matching.py
│       ├── test_as_quoter.py
│       ├── test_metrics.py
│       └── test_reproducibility.py   # same seed → identical output
│
├── frontend/                         # TS/React — interactive UI only
│   ├── package.json                  # pnpm
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json                 # strict, no any
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   ├── ws.ts                 # websocket client
│       │   └── rest.ts               # control endpoints
│       ├── state/
│       │   └── sessionStore.ts       # zustand or context
│       ├── components/
│       │   ├── OrderBookLadder.tsx
│       │   ├── DepthChart.tsx
│       │   ├── TradeTape.tsx
│       │   ├── InventoryChart.tsx
│       │   ├── PnLChart.tsx
│       │   ├── ParameterPanel.tsx
│       │   ├── ScenarioPanel.tsx
│       │   ├── InterventionToggles.tsx
│       │   └── MetricsDashboard.tsx
│       └── types/
│           └── messages.ts           # mirrors backend types.py (codegen target)
│
├── notebooks/
│   ├── 03_baseline.ipynb
│   ├── 04_finding1.ipynb
│   ├── 05_finding2.ipynb
│   ├── 06_finding3.ipynb
│   ├── 07_finding4.ipynb
│   └── _shared/
│       ├── load.py                   # parquet loaders
│       ├── plotting.py               # consistent matplotlib styling
│       └── stats.py                  # PnL aggregation helpers
│
├── results/                          # gitignored except for manifest stub
│   └── .gitkeep
│
└── scripts/
    ├── run_all_experiments.sh        # backend/runner cli for every manifest entry
    ├── render_all_figures.sh         # papermill execute every notebook
    └── build_findings_pdf.sh         # pandoc findings.md → findings.pdf
```

**Run-from-zero commands** (each service is a single command):

```
uv sync                                                # install backend
pnpm --dir frontend install                            # install frontend
uv run python -m backend.runner.cli run baseline_calm  # one experiment
uv run bash scripts/run_all_experiments.sh             # full reproducibility
uv run uvicorn backend.server.app:app --reload         # live UI backend
pnpm --dir frontend dev                                # live UI frontend
uv run bash scripts/render_all_figures.sh              # rebuild every figure
uv run bash scripts/build_findings_pdf.sh              # rebuild PDF
```

---

## 4. Data Model

All Python types use Pydantic v2 with strict validation. TypeScript mirrors generated via `datamodel-code-generator` or hand-kept (manual is fine at this scale).

### 4.1 Core simulation events

```python
class Side(StrEnum):
    BID = "bid"
    ASK = "ask"

class CounterpartyType(StrEnum):
    NOISE = "noise"
    INFORMED = "informed"
    MM = "mm"

class CounterpartyId(BaseModel):
    id: str             # "noise_07", "informed_02", "mm"
    type: CounterpartyType

class TickEvent(BaseModel):
    t: float            # sim seconds since start
    true_mid: float
    realised_vol: float # rolling estimate at this instant

class OrderEvent(BaseModel):
    t: float
    cp: CounterpartyId
    side: Side
    price: float | None # None = market order
    size: float
    order_id: str

class CancelEvent(BaseModel):
    t: float
    order_id: str

class FillEvent(BaseModel):
    t: float
    maker_cp: CounterpartyId
    taker_cp: CounterpartyId
    side: Side          # side from MAKER's perspective
    price: float
    size: float
    mid_at_fill: float
    maker_order_id: str

class QuoteUpdate(BaseModel):
    t: float
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    reservation_price: float
    half_spread: float
    inventory: float
    sigma_est: float
    gamma: float
    interventions_active: list[str]
```

### 4.2 State snapshots (websocket payloads)

```python
class L2Level(BaseModel):
    price: float
    size: float

class L2Snapshot(BaseModel):
    t: float
    bids: list[L2Level]    # top 20 levels
    asks: list[L2Level]
    mid: float

class MMState(BaseModel):
    t: float
    inventory: float
    cash: float
    realised_pnl: float
    unrealised_pnl: float
    total_pnl: float
    fills_total: int
    quote_uptime_pct: float
    sigma_est: float
    active_interventions: list[str]

class WsMessage(BaseModel):
    seq: int
    kind: Literal["snapshot", "fill", "quote_update", "metric_tick", "scenario_event", "log"]
    payload: dict[str, Any]   # one of the above models
```

### 4.3 Experiment config schema (`experiments.yaml`)

```yaml
- id: f1_gamma_sweep_low_vol
  finding: 1
  description: "Gamma sweep on calm GBM market"
  seeds: [42]
  duration_seconds: 14400
  market:
    process: gbm
    sigma_true: 0.01     # per sqrt(second)
    drift: 0
    initial_price: 100.0
  counterparties:
    noise:
      count: 16
      arrival_rate_hz: 5.0
      limit_fraction: 0.7
      cancel_halflife_s: 30
    informed:
      count: 0
  quoter:
    type: avellaneda_stoikov
    gamma_sweep: [0.01, 0.1, 0.5, 1.0, 5.0]
    k: 1.5
    tau: 300
    sigma_estimator:
      type: ewma
      halflife_s: 60
    refresh_ms: 100
    inventory_limit: 100
    spread_caps: { min: 0.0001, max: 0.1 }
  interventions: []
  events: []
  output_path: results/f1/gamma_sweep_low_vol
```

A *parameter sweep* (`gamma_sweep`) expands into one run per value × seed. The runner cross-products sweeps automatically.

### 4.4 Results schema (Parquet)

Per run (`results/<experiment_id>/<param_combo>/<seed>/`):

- `fills.parquet` — one row per fill: `t, side, price, size, mid_at_fill, maker_cp_id, taker_cp_id, drift_1s, drift_10s, drift_60s` (drifts computed at write time).
- `quotes.parquet` — one row per quote update.
- `inventory.parquet` — sampled at 1Hz: `t, inventory, cash, realised_pnl, unrealised_pnl, sigma_est`.
- `metrics_summary.json` — single object with totals: `total_pnl, spread_pnl, inventory_pnl, fees_paid, max_abs_inventory, time_at_limit_pct, quote_uptime_pct, fill_count, mean_post_fill_drift_*`.
- `config_snapshot.yaml` — exact resolved config used (no sweeps, just the concrete values).
- `run_metadata.json` — `git_sha, started_at_utc, finished_at_utc, wall_seconds, cpu_seconds, sim_engine_version`.

Notebooks read these via Polars (`pl.scan_parquet`) and aggregate.

### 4.5 REST control schema

```
POST /session/start         body: ExperimentConfig (or reference to manifest id)
POST /session/stop
POST /session/inject_event  body: { kind: ScenarioEventKind, params: {...} }
PATCH /session/parameters   body: partial Quoter config — live retune
PATCH /session/interventions body: { name: str, enabled: bool }
GET  /session/state         (snapshot, useful for reload)
GET  /experiments           list of manifest entries
```

WebSocket: `GET /ws` — server pushes `WsMessage` at ~10Hz coalesced.

---

## 5. Math Reference (Appendix to Findings)

### 5.1 The Avellaneda-Stoikov framework — what we use, what we don't

The original AS paper (2008) considers a market maker with a finite trading horizon `T`, modelling the optimal quotes that maximise expected utility of terminal wealth under inventory risk. We use the framework but make one principled deviation (D2): we replace the time-to-horizon `(T − t)` with a constant lookback `τ`, because we are simulating *continuous* market-making, not a one-shot end-of-day liquidation problem.

### 5.2 The reservation price

The MM's "fair value" is *not* the mid. It is the mid, adjusted by current inventory:

```
r(t) = s(t) − q(t) · γ · σ²(t) · τ
```

In words: if I am long `q`, I value the asset slightly *below* the market mid because I want to encourage someone to lift my offer and let me reduce inventory. The bigger my inventory, the more I shade. The shading is amplified by:

- `γ` — my **inventory aversion**. High γ = I really hate inventory; quotes shift aggressively.
- `σ²` — the variance of the underlying. Higher vol = inventory is more dangerous = stronger shading.
- `τ` — the "horizon" parameter. In AS this is `T − t`; we use a fixed lookback so the dynamics are stationary.

### 5.3 The optimal half-spread

```
δ_bid = δ_ask = (γ · σ² · τ) / 2  +  (1/γ) · ln(1 + γ/k)
```

Two terms with two intuitions:

1. `(γ · σ² · τ) / 2` — the **inventory-risk premium**. Even if no one trades adversely, I need this much edge to be compensated for the variance I'm holding. Scales with γ, σ², and lookback.
2. `(1/γ) · ln(1 + γ/k)` — the **monopoly-rent term**. This is what falls out of the assumed exponential intensity of market-order arrivals: `λ(δ) = A · exp(−k · δ)`. The MM captures rent from the gap between his quote and the touch — and `k` parameterises how price-elastic the order flow is. Low `k` = inelastic flow = MM widens to extract more rent. High `k` = very elastic = quotes tighten.

### 5.4 Final quotes

```
bid = r(t) − δ
ask = r(t) + δ
```

The asymmetry the MM displays is entirely encoded in `r(t)`: the spread itself is symmetric around the reservation price, but the reservation price moves with inventory.

### 5.5 What we estimate vs assume

- `s(t)` — observable from the L2 book mid.
- `σ(t)` — **estimated** with EWMA of squared returns (default 60s half-life). Cheat mode (D4) substitutes the generator's true σ for comparison.
- `γ` — **chosen by operator** (this is what Findings 1 and 4 sweep).
- `k` — **estimated** by fitting `λ(δ) = A·exp(−k·δ)` to a rolling window of fill data, OR fixed at a sensible default (1.5). We default to fixed in v1 — fitting introduces another source of variance we don't want yet.
- `τ` — **chosen by operator**, default 300s.
- `q(t)` — observed from our own fills.

### 5.6 Why this matters for the findings

- Finding 1 directly probes the `γ · σ² · τ` term — sweeping γ moves both the reservation-price tilt and the half-spread.
- Finding 2 demonstrates a phenomenon the AS model **does not capture**: post-fill drift from informed flow. The base AS model assumes symmetric noise traders. The penalty intervention is a hand-rolled extension that estimates a per-counterparty spread-widening multiplier from observed toxicity.
- Finding 4 shows that holding γ fixed across σ regimes is suboptimal — a direct consequence of `δ ∝ γσ²` being non-linear in γ.

---

## 6. UI Wireframe

Single-page layout, three columns. Designed to fit a 1440×900 laptop screen without scrolling for the live view. Tailwind utility classes; dark theme.

```
+------------------------------------------------------------------------------+
|  MM SIM — session: live_001    [▶ START] [⏸ PAUSE] [■ STOP]     SimT 00:42:13 |
|  Scenario: [Calm GBM ▼]   Inject ▶ [Sell-off][News][LiqWith][ToxicBurst]    |
+----------------------+--------------------------------+------------------------+
|  ORDER BOOK          |  PRICE & QUOTES                |  PARAMETERS           |
|                      |                                |                       |
|   ASK            BID |    [line: mid (white)]         | γ          0.10  [▿]  |
|   100.05  ─── 100.04 |    [line: bid (red dash)]      | k          1.5   [▿]  |
|   100.06     100.03  |    [line: ask (green dash)]    | τ (s)      300   [▿]  |
|   100.07     100.02  |    last 5 min, 1Hz             | EWMA hl    60s   [▿]  |
|   100.08     100.01  |                                | σ source [EWMA ▼]     |
|   100.09     100.00  |    fills overlaid as dots      |   ( ) cheat (true σ)  |
|                      |    sized by qty, coloured by   |                       |
|   [depth chart        |    side                        | INV LIMIT  100 [▿]    |
|    horizontal bar    |                                | SPREAD MIN 1bp  [▿]   |
|    histogram, top    |                                | SPREAD MAX 100bp[▿]   |
|    20 levels each    +--------------------------------+                       |
|    side]             |  INVENTORY                     | INTERVENTIONS         |
|                      |                                | [x] adaptive spread   |
|                      |    [signed line with limit     | [ ] kill switch       |
|                      |     bands shaded ±100]         | [ ] hedge on thresh   |
|                      |                                | [x] news detector     |
|                      +--------------------------------+ [ ] cp penalty        |
|                      |  PnL DECOMPOSITION             |                       |
|                      |    [stacked area:              | [Manual quote pull]   |
|                      |     spread / inventory / fees] | [Force flatten now]   |
|                      |                                |                       |
+----------------------+--------------------------------+------------------------+
|  TRADE TAPE                          |  METRICS DASHBOARD                     |
|  t       side  px      qty  taker    |  Total PnL          +$1,243.18         |
|  42:11.3 ASK  100.05    1.0 noise_07 |  Spread PnL         +$1,890.40         |
|  42:10.9 BID  100.03    0.5 inf_02   |  Inventory PnL       −$612.22          |
|  42:10.4 ASK  100.05    2.0 noise_11 |  Fees                 −$35.00          |
|  ...      auto-scrolling, max 50     |  Inventory             +12.0           |
|                                      |  Quote uptime         98.4%            |
|                                      |  Fills (last 60s)     34               |
|                                      |  Adv. sel. (10s)      −0.6 bp          |
|                                      |  Active CPs flagged toxic: inf_02, inf_04 |
+--------------------------------------+----------------------------------------+
|  LOG STREAM (collapsible, last 20 entries, structured)                       |
|  [INFO] 42:13.1 quote update bid=100.04 ask=100.05 inv=12 sigma=0.0103       |
|  [WARN] 42:11.0 informed fill detected: cp=inf_02 drift_10s=-0.7bp           |
|  [INFO] 42:10.0 intervention adaptive_spread engaged: σ_realised > 1.5×μ      |
+------------------------------------------------------------------------------+
```

Three "modes" of the same page:
- **Live mode** (above) — running session, all panels active.
- **Paused mode** — same layout, all sliders/toggles still functional, sim resumes from current state. Useful for "what if I changed γ here" demos.
- **Replay mode** — load a saved experiment run, scrub through with a timeline slider at the top.

---

## 7. Build Order & Milestones

Hard rule: **headless reproducibility before any UI**. The findings doc must build from `scripts/run_all_experiments.sh && scripts/render_all_figures.sh && scripts/build_findings_pdf.sh` before frontend work starts.

### Milestone 1 — Engine + Runner + Finding 1 reproducible (Days 1–4)

Goal: `bash scripts/run_all_experiments.sh f1_*` produces every Finding 1 chart.

- [ ] Project skeleton, pyproject, uv lock, basic CI (just `pytest` + `mypy --strict`).
- [ ] `mm_sim.types` — all Pydantic models from §4.1–4.4.
- [ ] `mm_sim.rng` — single source of randomness keyed by seed.
- [ ] `mm_sim.market.processes.GBM` — simplest generator. Validate σ via test.
- [ ] `mm_sim.market.book` + `matching` — naive sorted-list L2 book, single-thread match. Test: 1000 random orders → invariants hold.
- [ ] `mm_sim.traders.noise` — Poisson arrival of limits and markets, configurable rate.
- [ ] `mm_sim.quoter.vol_estimator.EWMA`.
- [ ] `mm_sim.quoter.avellaneda_stoikov` — infinite-horizon variant. Test against hand-computed reservation prices.
- [ ] `mm_sim.metrics.pnl` + `inventory` + `adverse_selection` (drift histograms only — no per-cp yet).
- [ ] `mm_sim.engine` — discrete time-stepped event loop, deterministic given seed. **Reproducibility test**: same seed twice → byte-identical parquet outputs.
- [ ] `mm_sim.results` — parquet writer.
- [ ] `runner.cli` + `runner.manifest` — load yaml, expand sweeps, run sequentially.
- [ ] `experiments.yaml` — Finding 1 entries only.
- [ ] `notebooks/04_finding1.ipynb` — generates all f1 charts.
- [ ] First draft of `docs/findings.md` §3 and §4 with real numbers.

**Done when:** I can re-run Finding 1 from a clean checkout in <15 min and get identical charts.

### Milestone 2 — Scenarios + Findings 2 & 3 reproducible (Days 5–8)

- [ ] `mm_sim.traders.informed` — D3 implementation, with 4-CP pool.
- [ ] `mm_sim.traders.counterparty` — stable IDs, attribution wiring through fills.
- [ ] `mm_sim.metrics.per_counterparty` — rolling toxicity estimator.
- [ ] `mm_sim.scenarios.library` — selloff, newsspike (uses jump-diffusion temporarily), liqwithdraw, toxicburst.
- [ ] `mm_sim.scenarios.timeline` — schedule events into the engine loop.
- [ ] `mm_sim.market.processes.JumpDiffusion` — for newsspike.
- [ ] `mm_sim.quoter.interventions` — all five intervention modules. Each independently switchable.
- [ ] `runner.batch` — multiprocessing across cores for f3's 16 runs and f4's 500 runs.
- [ ] Add Finding 2 & 3 entries to `experiments.yaml`.
- [ ] `notebooks/05_finding2.ipynb`, `06_finding3.ipynb`.
- [ ] Findings doc §5 and §6 drafted with real numbers.

**Done when:** entire Findings 0–3 section of the doc renders from scripts. Finding 3 grid contains at least one cell where intervention HURTS (the honest-analysis requirement).

### Milestone 3 — Finding 4 + Interactive UI (Days 9–12)

Two tracks; Finding 4 is a long batch run that can happen overnight while UI is built.

Track A — Finding 4 (mostly waiting):
- [ ] Add f4 grid to manifest.
- [ ] Run overnight on 8 cores.
- [ ] `notebooks/07_finding4.ipynb`. Findings doc §7.

Track B — UI (the bulk of these 4 days):
- [ ] FastAPI app with `/session/start` (in-memory single-session for simplicity).
- [ ] WebSocket coalescing engine state to ~10Hz `WsMessage` stream.
- [ ] Vite + React + TS + Tailwind scaffold. Strict TS.
- [ ] WebSocket client + zustand store.
- [ ] `OrderBookLadder` + `DepthChart` (Recharts).
- [ ] `PriceQuotes` overlay chart.
- [ ] `InventoryChart`, `PnLChart`.
- [ ] `ParameterPanel` with live PATCH wiring.
- [ ] `InterventionToggles`, `ScenarioPanel`.
- [ ] `MetricsDashboard`, `TradeTape`, `LogStream`.
- [ ] Replay mode: load a saved run's parquets, drive the same components from a timeline slider instead of a live socket.

**Done when:** I can demo a live session for 3 minutes, inject a sell-off, watch interventions trigger, retune γ live, and have it feel like an ops console.

### Milestone 4 — Findings PDF + README + Demo (Days 13–14)

- [ ] §1 Executive Summary, §2 The Setup, §8 What I'd Build Next, §9 What This Project Is Not.
- [ ] `math_appendix.md` polished and pulled into findings.md as Appendix A.
- [ ] `experiments.yaml` pulled in as Appendix B.
- [ ] `scripts/build_findings_pdf.sh` — pandoc with a clean template.
- [ ] README: pitch in 200 words, "how to run from scratch" in 5 commands, embedded `demo.gif`, link to `findings.pdf`.
- [ ] 3-min screen capture, optimised to <5MB GIF or hosted MP4.
- [ ] Final pass: every claim in findings has an experiment id; every chart filename matches a notebook output; PDF builds clean.

---

## 8. Risks & Unknowns

Things I'd want to flag or check in with you on as I go.

1. **Adverse-selection signal calibration (D3).** Getting informed traders to land at exactly 55–60% directional hit rate without making them dominate fill flow takes tuning. I'll expose `informed_signal_noise_std` as a knob and report measured hit rate per run. If after Milestone 2 the hit rate is unstable, I may need to redesign the informed-trader signal generator.

2. **`k` estimation.** Default is fixed `k=1.5`. If the headline claim "γ-σ interaction matters" turns out to depend strongly on `k`, I'll need to either fit `k` from rolling fill data or sweep it as a sensitivity check in §7. Flagging now: I'd rather defend a fixed-k assumption than get tangled in fitting if results are clear without it.

3. **Reproducibility on Windows.** Engine determinism across multiprocessing on Windows can be tricky (different worker startup paths, BLAS thread state). Will pin `OMP_NUM_THREADS=1` for runners and add a CI test that compares hashes across runs. If determinism becomes flaky, fall back to single-process for the canonical chart-producing runs and use multiprocessing only for f4's grid (where seed-level reproducibility per cell is enough).

4. **Finding 3 honest-analysis requirement.** The spec demands at least three charts where an intervention hurts. I have anticipated candidates (kill switch in liquidity-withdrawal, etc.) but won't know they actually hurt until I run it. If after Milestone 2 every intervention helps everywhere, I'll deliberately introduce a poorly-tuned intervention variant (e.g., kill switch with too-tight threshold) so the finding stays honest.

5. **Finding 4 runtime.** Estimated ~4hr single-thread. If it pushes over 8hr in practice I'll trim to 4×4 grid with fewer seeds, or run only the slice along the diagonal plus the optimum trace.

6. **What "PnL" means at session end with open inventory.** Need to decide: liquidate at terminal mid (clean, but ignores liquidation cost) or report inventory PnL separately and not mark to liquidation cost. Defaulting to the latter (mark to mid, no liquidation slippage charge) and documenting it. Flag if you want simulated terminal liquidation through the book instead.

7. **Frontend chart performance.** Recharts is fine for ~1000 points but will choke on a 4hr session at 10Hz. Will downsample server-side to ~5min rolling windows for live charts; full data only available in replay mode where the user expects scrubbing. If Recharts is still sluggish, swap to lightweight-charts for the price/PnL panels (kept Recharts as default because it's simpler).

8. **Single biggest unknown:** whether the adverse-selection penalty intervention (Finding 2) will actually outperform global widening. The penalty needs enough fills per CP to learn from before the session ends. If 4hr × 4 informed CPs isn't enough fills to learn meaningfully, the headline of Finding 2 weakens. Mitigation: bump session length for that experiment to 8hr, or pre-warm the toxicity estimator with a "training" prequel.

---

## 9. Scope Discipline — Explicitly NOT Building

To keep this to ~2 weeks part-time:

- **No real exchange connectivity.** No CCXT, no websockets to Binance, no shadow-quote mode. Out of scope. Listed in §8 as future work.
- **No multi-asset.** Single instrument throughout.
- **No multi-venue.** Single book throughout.
- **No real fee schedules / rebates.** Single configurable `taker_fee_bps` and `maker_rebate_bps`. No tiered VIP, no per-pair differences.
- **No latency modelling beyond quote refresh tick.** No order-to-exchange latency, no cancel-replace race conditions, no queue-position simulation.
- **No ML.** No informed-trader detection by classifier, no learned market-making policies, no RL.
- **No real microstructure.** No iceberg orders, no auction phases, no MBO data, no pro-rata matching, no self-trade prevention beyond a stub.
- **No risk system.** Inventory limit is a hard kill switch, not a layered VAR/Greek/concentration framework.
- **No persistence beyond parquet results.** No database, no historical session browser in UI, no user accounts. Replay mode loads from disk only.
- **No deployment.** Local-only. No Docker, no cloud, no CI beyond unit tests.
- **No paid services or APIs.**

Things I will *not* polish:
- Frontend doesn't need to be pretty beyond functional. Tailwind defaults, no design system.
- Logging is structured but no log shipping / dashboards.
- No mobile responsiveness.
- No accessibility audit.

If at end of Milestone 4 there's still time: highest-value adds are (a) the adaptive γ scheduler from §8 of the findings (could itself become a Finding 5), and (b) the shadow-mode connectivity for talking-points value. Neither is in the base scope.

---

## Appendix A — How to challenge this plan

If you want to redirect, the levers in rough order of structural impact:

- **Bigger:** add Finding 5 on adaptive γ scheduling (becomes the "and here's how I'd actually fix it" finding). Adds ~2 days.
- **Smaller:** drop Finding 4 entirely, lean harder on Findings 2 and 3. Saves ~3 days.
- **Different framing:** make the centrepiece a single deep dive on adverse selection (current Finding 2 expanded), and demote 1/3/4 to appendices. Probably the strongest narrative if the hiring story is "I understand the silent killer." Talk to me before I start Milestone 1 if this resonates.
- **Tooling swaps:** replace Recharts with lightweight-charts (better for finance UIs but less ergonomic). Replace Pydantic with attrs (faster, less convenient). Replace Polars with pandas (simpler, slower at scale — fine here).
