// WebSocket pump: receives messages off the main thread's render path,
// buffers chart updates for a 10 Hz flush, and dispatches control events
// (scenario / intervention) to the controls store immediately.

import { useChartStore, type ChartTick } from "../state/chartStore";
import { useSessionStore } from "../state/sessionStore";
import type {
  FillPayload,
  InterventionEventPayload,
  L2Snapshot,
  ScenarioEventPayload,
  WsMessage,
} from "../types/messages";

const FLUSH_MS = 100; // 10 Hz UI update cap

let ws: WebSocket | null = null;
let cancelled = true;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let flushTimer: ReturnType<typeof setInterval> | null = null;
let pendingTicks: ChartTick[] = [];
let pendingFills: FillPayload[] = [];
let pendingSnapshot: L2Snapshot | null = null;
let refCount = 0;

function flush(): void {
  if (pendingTicks.length) {
    useChartStore.getState().appendTicks(pendingTicks);
    pendingTicks = [];
  }
  if (pendingFills.length) {
    useChartStore.getState().appendFills(pendingFills);
    pendingFills = [];
  }
  if (pendingSnapshot) {
    useChartStore.getState().setSnapshot(pendingSnapshot);
    pendingSnapshot = null;
  }
}

function handle(msg: WsMessage): void {
  if (msg.kind === "quote_update") {
    const p = msg.payload as Record<string, number | string[] | null>;
    const num = (v: unknown) => (v == null ? NaN : Number(v));
    pendingTicks.push({
      t: Number(p.t),
      mid: Number(p.mid),
      fills_count: Number(p.fills_count),
      inventory: Number(p.inventory),
      total_pnl: Number(p.total_pnl),
      spread_pnl: Number(p.spread_pnl),
      inventory_pnl: Number(p.inventory_pnl),
      sigma_est: Number(p.sigma_est),
      reservation_price: num(p.reservation_price),
      half_spread: num(p.half_spread),
      inv_risk_term: num(p.inv_risk_term),
      rent_term: num(p.rent_term),
      active_interventions: (p.active_interventions as string[]) ?? [],
    });
  } else if (msg.kind === "snapshot") {
    pendingSnapshot = msg.payload as unknown as L2Snapshot;
  } else if (msg.kind === "fill") {
    pendingFills.push(msg.payload as unknown as FillPayload);
  } else if (msg.kind === "scenario_event") {
    // Dispatched immediately — keeps the events log responsive
    useSessionStore.getState().pushEvent(msg.payload as unknown as ScenarioEventPayload);
  } else if (msg.kind === "intervention_event") {
    useSessionStore
      .getState()
      .pushIntervention(msg.payload as unknown as InterventionEventPayload);
  }
}

function open(): void {
  if (cancelled) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    try {
      handle(JSON.parse(ev.data) as WsMessage);
    } catch {
      /* ignore non-JSON */
    }
  };
  ws.onclose = () => {
    if (cancelled) return;
    reconnectTimer = setTimeout(open, 500);
  };
}

export function startWsPump(): void {
  refCount += 1;
  if (refCount > 1) return; // already running
  cancelled = false;
  pendingTicks = [];
  pendingFills = [];
  pendingSnapshot = null;
  flushTimer = setInterval(flush, FLUSH_MS);
  open();
}

export function stopWsPump(): void {
  refCount = Math.max(0, refCount - 1);
  if (refCount > 0) return; // still in use
  cancelled = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (flushTimer) {
    clearInterval(flushTimer);
    flushTimer = null;
  }
  ws?.close();
  ws = null;
}
