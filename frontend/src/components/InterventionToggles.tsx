import { useState } from "react";
import { api } from "../api/rest";
import { CUSTOM_REGIME_KEY } from "../state/regimes";
import { useSessionStore } from "../state/sessionStore";

const NAMES: { name: string; label: string; tooltip: string }[] = [
  {
    name: "adaptive_spread",
    label: "Adaptive spread",
    tooltip:
      "Multiplicatively widens the half-spread when realised volatility (σ_est) exceeds the baseline σ_true. Trades fill rate for protection during vol spikes.",
  },
  {
    name: "kill_switch",
    label: "Kill switch",
    tooltip:
      "Cancels all MM quotes when |inventory| exceeds inventory_limit × kill_switch_inventory_pct (default 90%). Stops bleeding while inventory recovers.",
  },
  {
    name: "news_detector",
    label: "News detector",
    tooltip:
      "Detects sudden mid jumps (≥ news_detector_jump_bps) between quote refreshes and pulls quotes for one cycle. Designed to dodge stale-quote pickoffs after news shocks.",
  },
  {
    name: "hedge_on_threshold",
    label: "Hedge on threshold",
    tooltip:
      "When |inventory| crosses hedge_threshold_pct × inventory_limit (default 70%), the MM submits a market order back toward zero inventory. Pays the spread to reduce risk.",
  },
  {
    name: "per_counterparty_penalty",
    label: "Per-CP penalty",
    tooltip:
      "Tracks per-counterparty post-fill drift; quotes shown to historically toxic counterparties get widened. Trades fill rate vs. those CPs for less adverse selection.",
  },
];

export function InterventionToggles() {
  const intr = useSessionStore((s) => s.state.interventions ?? {});
  const patchLocal = useSessionStore((s) => s.patchInterventionLocal);
  const setState = useSessionStore((s) => s.setState);
  const setRegime = useSessionStore((s) => s.setRegime);
  const running = useSessionStore((s) => s.state.running);
  const [hovered, setHovered] = useState<string | null>(null);
  const info = NAMES.find((n) => n.name === hovered);
  return (
    <div className="panel p-3">
      <div className="label mb-2">Interventions</div>
      {NAMES.map((it) => (
        <label
          key={it.name}
          className="flex items-center justify-between text-xs py-1 cursor-pointer"
          onMouseEnter={() => setHovered(it.name)}
          onFocus={() => setHovered(it.name)}
        >
          <span>{it.label}</span>
          <input
            type="checkbox"
            checked={!!intr[it.name]}
            disabled={!running}
            onChange={async (e) => {
              const next = e.target.checked;
              setRegime(CUSTOM_REGIME_KEY);
              patchLocal(it.name, next);
              try {
                await api.patchIntervention(it.name, next);
                const fresh = await api.state();
                setState(fresh);
              } catch {
                patchLocal(it.name, !next);
              }
            }}
          />
        </label>
      ))}
      <div className="mt-2 p-2 bg-bg/60 border border-border rounded text-[10px] text-sub leading-snug min-h-[44px]">
        {info ? (
          <>
            <span className="text-ink font-semibold">{info.label}.</span> {info.tooltip}
          </>
        ) : (
          <span className="italic">Hover an intervention to see what it does.</span>
        )}
      </div>
    </div>
  );
}
