import { useSessionStore } from "../state/sessionStore";

export function MetricsDashboard() {
  const state = useSessionStore((s) => s.state);
  const ticks = useSessionStore((s) => s.ticks);
  const last = ticks[ticks.length - 1];

  const total = last?.total_pnl ?? state.total_pnl ?? 0;
  const spread = last?.spread_pnl ?? state.spread_pnl ?? 0;
  const inv = last?.inventory_pnl ?? state.inventory_pnl ?? 0;
  const inventory = last?.inventory ?? state.inventory ?? 0;
  const sigma = last?.sigma_est ?? state.sigma_est ?? 0;
  const t = last?.t ?? state.sim_t ?? 0;

  return (
    <div className="panel p-3">
      <div className="label mb-2">Live Metrics</div>
      <Stat label="Sim time (s)" value={t.toFixed(1)} />
      <Stat label="Total PnL" value={`$${total.toFixed(2)}`} highlight={total >= 0 ? "ok" : "bad"} />
      <Stat label="Spread PnL" value={`$${spread.toFixed(2)}`} />
      <Stat label="Inventory PnL" value={`$${inv.toFixed(2)}`} />
      <Stat label="Inventory" value={inventory.toFixed(2)} />
      <Stat label="σ est (per √s)" value={sigma.toFixed(5)} />
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: "ok" | "bad" }) {
  const cls = highlight === "ok" ? "text-ask" : highlight === "bad" ? "text-bid" : "text-ink";
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-sub">{label}</span>
      <span className={`font-semibold ${cls}`}>{value}</span>
    </div>
  );
}
