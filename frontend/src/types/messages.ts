// Mirrors backend mm_sim.types — keep in sync manually.

export type Side = "bid" | "ask";

export interface L2Level { price: number; size: number; }
export interface L2Snapshot { t: number; bids: L2Level[]; asks: L2Level[]; mid: number; }

export interface MMState {
  t: number; inventory: number; cash: number;
  realised_pnl: number; unrealised_pnl: number; total_pnl: number;
  fills_total: number; quote_uptime_pct: number; sigma_est: number;
  active_interventions: string[];
}

export interface QuoteUpdatePayload {
  t: number; mid: number; fills_count: number; inventory: number;
  total_pnl: number; spread_pnl: number; inventory_pnl: number;
  sigma_est: number; active_interventions: string[];
}

export interface ScenarioEventPayload {
  t: number; kind: string; params: Record<string, unknown>; source?: string;
}

export interface InterventionEventPayload {
  t: number; kind: string; action: string; details?: Record<string, unknown>;
}

export interface FillPayload {
  t: number;
  price: number;
  size: number;
  aggressor: "buy" | "sell";
  mid: number;
  mm: boolean;
}

export type WsKind = "snapshot" | "fill" | "quote_update" | "metric_tick" | "scenario_event" | "log";

export interface WsMessage {
  seq: number;
  kind: WsKind;
  payload: Record<string, unknown>;
}

export interface SessionState {
  running: boolean; paused?: boolean; experiment_id?: string;
  sim_t?: number; inventory?: number;
  total_pnl?: number; spread_pnl?: number; inventory_pnl?: number;
  sigma_est?: number;
  gamma?: number; k?: number; tau?: number;
  q_target?: number;
  bid_widening_factor?: number;
  ask_widening_factor?: number;
  inventory_limit?: number;
  interventions?: Record<string, boolean>;
  intervention_params?: {
    kill_switch_inventory_pct?: number;
    hedge_threshold_pct?: number;
    adaptive_spread_mult_per_vol?: number;
    news_detector_jump_bps?: number;
    cp_penalty_decay_halflife_s?: number;
  };
}

export interface Experiment { id: string; finding: number; description: string; }
