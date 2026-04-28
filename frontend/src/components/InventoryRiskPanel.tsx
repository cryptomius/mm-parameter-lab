import { useState } from "react";
import { api } from "../api/rest";
import { useChartStore } from "../state/chartStore";
import { CUSTOM_REGIME_KEY } from "../state/regimes";
import { useSessionStore } from "../state/sessionStore";
import { Slider } from "./Slider";

const META: Record<string, { label: string; description: string }> = {
  inventory_limit: {
    label: "Inventory limit",
    description:
      "Hard cap on |inventory| in units of the quoted asset. Set this from your real risk budget — for a single-platform MM with no external hedge, this is the maximum directional exposure you're willing to carry. Both kill_switch and hedge_on_threshold compute their triggers as a percentage of this value. q_target is also bounded by ±limit.",
  },
  kill_switch_inventory_pct: {
    label: "Kill-switch %",
    description:
      "Kill switch fires when |inv| ≥ this fraction of the limit. Findings recommend ≥ 0.9 — treat as a circuit breaker, not a soft brake. Lower values trip on benign accumulation in slow markets (Finding 6.3 lost $404 of $488 with 0.4).",
  },
  hedge_threshold_pct: {
    label: "Hedge %",
    description:
      "Hedge fires when |inv| ≥ this fraction of the limit. Each hedge consumes opposite-side liquidity (pays the spread). For single-platform MMs with no external hedge, this is your only inventory-flattening mechanism — use cautiously. Set ≥ kill-switch and the hedge will fire first.",
  },
};

export function InventoryRiskPanel() {
  const limit = useSessionStore((s) => s.state.inventory_limit ?? 100);
  const ksOn = useSessionStore((s) => s.state.interventions?.kill_switch ?? false);
  const hgOn = useSessionStore((s) => s.state.interventions?.hedge_on_threshold ?? false);
  const ksPct = useSessionStore((s) => s.state.intervention_params?.kill_switch_inventory_pct ?? 0.9);
  const hgPct = useSessionStore((s) => s.state.intervention_params?.hedge_threshold_pct ?? 0.7);
  const running = useSessionStore((s) => s.state.running);
  const setRegime = useSessionStore((s) => s.setRegime);
  const [hovered, setHovered] = useState<string | null>(null);
  const info = hovered ? META[hovered] : null;

  // Live |inv| and peak from chart store. Use a selector that returns
  // primitives so we only re-render when these specific numbers change.
  const liveInv = useChartStore((s) => {
    const last = s.ticks[s.ticks.length - 1];
    return last ? Math.abs(last.inventory) : 0;
  });
  const peakInv = useChartStore((s) => {
    let max = 0;
    for (const t of s.ticks) {
      const a = Math.abs(t.inventory);
      if (a > max) max = a;
    }
    return max;
  });

  const ksAbs = limit * ksPct;
  const hgAbs = limit * hgPct;

  // Status colour for the live readout
  const status =
    ksOn && liveInv >= ksAbs
      ? { dot: "bg-bid", text: "text-bid", label: "kill-switch range" }
      : hgOn && liveInv >= hgAbs
        ? { dot: "bg-warn", text: "text-warn", label: "hedge range" }
        : { dot: "bg-ask", text: "text-ask", label: "ok" };

  const onLimitCommit = async (v: number) => {
    setRegime(CUSTOM_REGIME_KEY);
    await api.patchParams({ inventory_limit: v });
  };
  const onKsCommit = async (v: number) => {
    setRegime(CUSTOM_REGIME_KEY);
    await api.patchInterventionParams({ kill_switch_inventory_pct: v });
  };
  const onHgCommit = async (v: number) => {
    setRegime(CUSTOM_REGIME_KEY);
    await api.patchInterventionParams({ hedge_threshold_pct: v });
  };

  return (
    <div className="panel p-3">
      <div className="label mb-2">Inventory Risk Budget</div>
      <Slider
        label={META.inventory_limit.label}
        serverValue={limit}
        min={5}
        max={1000}
        scale="linear"
        disabled={!running}
        onCommit={onLimitCommit}
        onHover={setHovered}
        hoverKey="inventory_limit"
      />
      <div className="text-[10px] mb-2 px-1 space-y-0.5">
        <div className="flex justify-between text-sub">
          <span>Kill-switch fires at</span>
          <span className={ksOn ? "text-ink" : "text-sub italic"}>
            ±{ksAbs.toFixed(1)} ({(ksPct * 100).toFixed(0)}% of limit) {ksOn ? "" : "(off)"}
          </span>
        </div>
        <div className="flex justify-between text-sub">
          <span>Hedge fires at</span>
          <span className={hgOn ? "text-ink" : "text-sub italic"}>
            ±{hgAbs.toFixed(1)} ({(hgPct * 100).toFixed(0)}% of limit) {hgOn ? "" : "(off)"}
          </span>
        </div>
      </div>
      <div className="flex items-center justify-between text-[10px] mb-2 px-1">
        <div className="flex items-center gap-1.5">
          <span className={`inline-block w-2 h-2 rounded-full ${status.dot}`} />
          <span className="text-sub">live |inv|</span>
          <span className={`font-semibold ${status.text}`}>{liveInv.toFixed(2)}</span>
        </div>
        <div className="text-sub">
          peak {peakInv.toFixed(2)}
        </div>
      </div>
      <Slider
        label={META.kill_switch_inventory_pct.label}
        serverValue={ksPct}
        min={0.5}
        max={1.0}
        scale="linear"
        unit="×"
        disabled={!running || !ksOn}
        onCommit={onKsCommit}
        onHover={setHovered}
        hoverKey="kill_switch_inventory_pct"
      />
      <Slider
        label={META.hedge_threshold_pct.label}
        serverValue={hgPct}
        min={0.3}
        max={Math.min(0.95, ksPct)}
        scale="linear"
        unit="×"
        disabled={!running || !hgOn}
        onCommit={onHgCommit}
        onHover={setHovered}
        hoverKey="hedge_threshold_pct"
      />
      <div className="mt-2 p-2 bg-bg/60 border border-border rounded text-[10px] text-sub leading-snug min-h-[64px]">
        {info ? (
          <>
            <span className="text-ink font-semibold">{info.label}.</span> {info.description}
          </>
        ) : (
          <span className="italic">
            Single-platform MM has no external hedge — this is your only directional risk control. Hover a slider for guidance.
          </span>
        )}
      </div>
    </div>
  );
}
