import { memo } from "react";
import { useChartStore } from "../state/chartStore";
import { useSessionStore } from "../state/sessionStore";

function MetricsDashboardImpl() {
  const last = useChartStore((s) => (s.ticks.length ? s.ticks[s.ticks.length - 1] : null));
  const fallbackT = useSessionStore((s) => s.state.sim_t ?? 0);
  const fallbackTotal = useSessionStore((s) => s.state.total_pnl ?? 0);
  const fallbackSpread = useSessionStore((s) => s.state.spread_pnl ?? 0);
  const fallbackInv = useSessionStore((s) => s.state.inventory ?? 0);
  const fallbackInvPnl = useSessionStore((s) => s.state.inventory_pnl ?? 0);
  const fallbackSigma = useSessionStore((s) => s.state.sigma_est ?? 0);

  const total = last?.total_pnl ?? fallbackTotal;
  const spread = last?.spread_pnl ?? fallbackSpread;
  const inv = last?.inventory_pnl ?? fallbackInvPnl;
  const inventory = last?.inventory ?? fallbackInv;
  const sigma = last?.sigma_est ?? fallbackSigma;
  const t = last?.t ?? fallbackT;

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

export const MetricsDashboard = memo(MetricsDashboardImpl);
