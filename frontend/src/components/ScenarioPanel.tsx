import { useState } from "react";
import { api } from "../api/rest";
import { useSessionStore } from "../state/sessionStore";

const EVENTS = [
  {
    kind: "selloff",
    label: "Sell-off",
    params: { size: 60 },
    tooltip:
      "Submits a single 60-unit market sell that walks the bid book. Tests how the MM absorbs a one-sided liquidity shock.",
  },
  {
    kind: "buyin",
    label: "Buy-in",
    params: { size: 60 },
    tooltip:
      "Mirror of sell-off: a 60-unit market buy walking the ask book. Tests upside-shock inventory accumulation.",
  },
  {
    kind: "newsspike",
    label: "News spike",
    params: { log_jump: 0.015, sigma_mult: 4, vol_duration_s: 90 },
    tooltip:
      "Instant +1.5% log-price jump plus 90s of 4× elevated volatility. Models a news event that strands stale quotes.",
  },
  {
    kind: "liqwithdraw",
    label: "Liquidity withdrawal",
    params: { multiplier: 0.2, duration_s: 600 },
    tooltip:
      "Cuts noise-trader arrival rate to 20% for 10 minutes. Models thin-book regimes where the MM is the only quoter.",
  },
  {
    kind: "toxicburst",
    label: "Toxic burst",
    params: { multiplier: 8, duration_s: 120 },
    tooltip:
      "Multiplies informed-trader arrival rate by 8× for 2 minutes. Tests defences (per-CP penalty, adaptive spread) against a toxic-flow burst.",
  },
];

export function ScenarioPanel() {
  const events = useSessionStore((s) => s.events);
  const running = useSessionStore((s) => s.state.running);
  const [hovered, setHovered] = useState<string | null>(null);
  const info = EVENTS.find((e) => e.kind === hovered);
  return (
    <div className="panel p-3">
      <div className="label mb-2">Inject Scenario</div>
      <div className="grid grid-cols-2 gap-1">
        {EVENTS.map((ev) => (
          <button
            key={ev.kind}
            className="btn text-left disabled:opacity-40"
            disabled={!running}
            onMouseEnter={() => setHovered(ev.kind)}
            onFocus={() => setHovered(ev.kind)}
            onClick={() => api.inject(ev.kind, ev.params)}
          >
            {ev.label}
          </button>
        ))}
      </div>
      <div className="mt-2 p-2 bg-bg/60 border border-border rounded text-[10px] text-sub leading-snug min-h-[44px]">
        {info ? (
          <>
            <span className="text-ink font-semibold">{info.label}.</span> {info.tooltip}
          </>
        ) : (
          <span className="italic">Hover a scenario to see what it injects.</span>
        )}
      </div>
      <div className="label mt-3 mb-1">Recent events</div>
      <div className="text-[10px] font-mono max-h-40 overflow-y-auto space-y-0.5">
        {events.length === 0 && <div className="text-sub">none yet</div>}
        {events.map((e) => {
          if (e.category === "scenario") {
            return (
              <div key={e.id} className="flex justify-between gap-2">
                <span className="text-sub">t={e.t.toFixed(1)}s</span>
                <span className="text-warn">⚡ {e.kind}</span>
                <span className="text-sub truncate">{e.source ?? "scheduled"}</span>
              </div>
            );
          }
          const det = e.details ?? {};
          const summary =
            e.action === "hedge_fill"
              ? `${det.side} ${(det.size as number)?.toFixed(2)} @ ${(det.price as number)?.toFixed(2)}`
              : e.action === "quotes_pulled"
                ? `inv=${(det.inventory as number)?.toFixed(1)}`
                : "";
          return (
            <div key={e.id} className="flex justify-between gap-2">
              <span className="text-sub">t={e.t.toFixed(1)}s</span>
              <span className="text-ask">🛡 {e.kind}</span>
              <span className="text-sub truncate">{summary}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
