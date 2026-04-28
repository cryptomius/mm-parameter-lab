// Operating-regime presets for the MM. Each regime bundles a set of quoter
// parameters and a set of intervention flags. Selecting a regime PATCHes
// these to the backend in one shot. Editing any individual control after a
// regime is selected switches the dropdown to "custom".
//
// Risk-budget values (inventory_limit, kill_switch_inventory_pct,
// hedge_threshold_pct) are deliberately NOT part of the bundle — those are
// operator-set in the InventoryRiskPanel. Each regime DESCRIBES recommended
// values via `recommendedRiskBudget` so the operator can apply them
// deliberately.

export interface InterventionFlags {
  adaptive_spread: boolean;
  kill_switch: boolean;
  news_detector: boolean;
  hedge_on_threshold: boolean;
  per_counterparty_penalty: boolean;
}

export interface RecommendedRiskBudget {
  inventory_limit: number;
  kill_switch_inventory_pct?: number;  // omit when intervention is off
  hedge_threshold_pct?: number;        // omit when intervention is off
}

export interface Regime {
  key: string;
  label: string;
  // 1-2 sentence description shown on hover. Should explain WHEN to use it.
  description: string;
  // Quoter knobs applied via PATCH /api/session/parameters
  params: {
    gamma: number;
    k: number;
    tau: number;
    q_target: number;
    bid_widening_factor: number;
    ask_widening_factor: number;
  };
  // Intervention on/off flags applied via PATCH /api/session/interventions
  interventions: InterventionFlags;
  // Recommended risk-budget values shown to the operator (NOT auto-applied).
  recommendedRiskBudget: RecommendedRiskBudget;
}

export const CUSTOM_REGIME_KEY = "custom";

export const REGIMES: Regime[] = [
  {
    key: "calm_spread_capture",
    label: "Calm spread capture (default)",
    description:
      "Vanilla AS at default knobs. Use this as the at-rest reference for what AS does without operator overrides. Matches the baseline_calm experiment in the findings.",
    params: { gamma: 0.1, k: 10, tau: 300, q_target: 0, bid_widening_factor: 1, ask_widening_factor: 1 },
    interventions: {
      adaptive_spread: false, kill_switch: false, news_detector: false,
      hedge_on_threshold: false, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 100 },
  },
  {
    key: "high_inventory_aversion",
    label: "High inventory aversion (recommended baseline)",
    description:
      "γ = 5 — the Finding 1 result. ~53% PnL lift and 87% peak-|inv| reduction vs default in the regimes tested. adaptive_spread on as cheap insurance. Recommended baseline once you've seen the default.",
    params: { gamma: 5, k: 10, tau: 300, q_target: 0, bid_widening_factor: 1, ask_widening_factor: 1 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: false, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 100, kill_switch_inventory_pct: 0.9 },
  },
  {
    key: "structural_sell_pressure",
    label: "Structural sell pressure (e.g. token vesting)",
    description:
      "Persistent one-sided sell flow (vesting unlocks, allocation distributions). Pre-skews short via q_target = -25, fattens the bid (less aggressive on accumulation), tightens the ask (sheds long inventory faster). Adaptive spread on; hedge_on_threshold ready for manual review when triggered. Recommend lowering inventory_limit (~50) and setting hedge ≈ 0.85 in the Inventory Risk panel.",
    params: { gamma: 5, k: 10, tau: 300, q_target: -25, bid_widening_factor: 1.5, ask_widening_factor: 0.7 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: true, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 50, kill_switch_inventory_pct: 0.9, hedge_threshold_pct: 0.85 },
  },
  {
    key: "structural_buy_pressure",
    label: "Structural buy pressure (e.g. buyback)",
    description:
      "Mirror of vesting. Persistent one-sided buy flow — pre-skews long via q_target = +25, tightens the bid (sheds short inventory faster), fattens the ask. Same risk-budget recommendations as the sell-pressure regime.",
    params: { gamma: 5, k: 10, tau: 300, q_target: 25, bid_widening_factor: 0.7, ask_widening_factor: 1.5 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: true, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 50, kill_switch_inventory_pct: 0.9, hedge_threshold_pct: 0.85 },
  },
  {
    key: "high_vol",
    label: "High vol / news-prone",
    description:
      "Lower γ to recapture turnover under elevated vol; shorter τ for faster inventory-skew response. Adaptive on. kill_switch and news_detector deliberately OFF — both have known failure modes (news_detector retriggers in post-event noise; see findings §6).",
    params: { gamma: 1, k: 10, tau: 180, q_target: 0, bid_widening_factor: 1, ask_widening_factor: 1 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: false, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 100, kill_switch_inventory_pct: 0.9 },
  },
  {
    key: "thin_book",
    label: "Thin book / low liquidity",
    description:
      "Slow flow regime (session boundaries, exchange degradation, quiet markets). Both spreads slightly wider; lower limit. kill_switch deliberately OFF — Finding 6.3 showed a tight kill_switch lost 83% of PnL in this regime by tripping on benign accumulation.",
    params: { gamma: 5, k: 10, tau: 300, q_target: 0, bid_widening_factor: 1.2, ask_widening_factor: 1.2 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: false, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 50, kill_switch_inventory_pct: 0.95 },
  },
  {
    key: "toxic_flow_burst",
    label: "Toxic-flow burst (manual review)",
    description:
      "Adverse-selection-suspected mode. Globally widens both sides via factors=1.5 (the global-widen path that kept 96% of PnL in §5 vs the per-CP penalty's 1%). Per-CP penalty stays OFF until rewritten. Treat as a temporary posture pending a CP-level rate cap or operator review.",
    params: { gamma: 1, k: 20, tau: 300, q_target: 0, bid_widening_factor: 1.5, ask_widening_factor: 1.5 },
    interventions: {
      adaptive_spread: true, kill_switch: false, news_detector: false,
      hedge_on_threshold: false, per_counterparty_penalty: false,
    },
    recommendedRiskBudget: { inventory_limit: 100, kill_switch_inventory_pct: 0.9 },
  },
];

export function findRegime(key: string): Regime | undefined {
  return REGIMES.find((r) => r.key === key);
}
