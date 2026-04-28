import { useState } from "react";
import { CUSTOM_REGIME_KEY, REGIMES, findRegime } from "../state/regimes";
import { useSessionStore } from "../state/sessionStore";

export function RegimeSelector() {
  const regime = useSessionStore((s) => s.regime);
  const applyRegime = useSessionStore((s) => s.applyRegime);
  const running = useSessionStore((s) => s.state.running);
  const [busy, setBusy] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  const onChange = async (key: string) => {
    if (key === CUSTOM_REGIME_KEY) return;
    setBusy(true);
    try {
      await applyRegime(key);
    } finally {
      setBusy(false);
    }
  };

  const onReapply = async () => {
    if (regime === CUSTOM_REGIME_KEY) return;
    setBusy(true);
    try {
      await applyRegime(regime);
    } finally {
      setBusy(false);
    }
  };

  const shown = hovered ?? regime;
  const info = shown !== CUSTOM_REGIME_KEY ? findRegime(shown) : null;

  return (
    <div className="panel p-3">
      <div className="label mb-2 flex items-center justify-between">
        <span>Operating Regime</span>
        {regime !== CUSTOM_REGIME_KEY && (
          <button
            className="text-[10px] text-sub hover:text-ink disabled:opacity-40"
            disabled={!running || busy}
            onClick={onReapply}
            title="Re-apply this regime's parameters and intervention flags."
          >
            ↻ reapply
          </button>
        )}
      </div>
      <select
        className="input w-full"
        value={regime}
        disabled={!running || busy}
        onChange={(e) => onChange(e.target.value)}
        onMouseLeave={() => setHovered(null)}
      >
        {REGIMES.map((r) => (
          <option
            key={r.key}
            value={r.key}
            onMouseEnter={() => setHovered(r.key)}
            onFocus={() => setHovered(r.key)}
          >
            {r.label}
          </option>
        ))}
        {regime === CUSTOM_REGIME_KEY && (
          <option key={CUSTOM_REGIME_KEY} value={CUSTOM_REGIME_KEY}>
            Custom (you've edited a control)
          </option>
        )}
      </select>
      <div className="mt-2 p-2 bg-bg/60 border border-border rounded text-[10px] text-sub leading-snug min-h-[64px]">
        {info ? (
          <>
            <span className="text-ink font-semibold">{info.label}.</span> {info.description}
            {info.recommendedRiskBudget && (
              <div className="mt-1 text-[10px]">
                <span className="text-warn">Recommended risk budget:</span>{" "}
                inventory_limit {info.recommendedRiskBudget.inventory_limit}
                {info.recommendedRiskBudget.kill_switch_inventory_pct != null &&
                  `, kill ${(info.recommendedRiskBudget.kill_switch_inventory_pct * 100).toFixed(0)}%`}
                {info.recommendedRiskBudget.hedge_threshold_pct != null &&
                  `, hedge ${(info.recommendedRiskBudget.hedge_threshold_pct * 100).toFixed(0)}%`}
                {" "}— set in the Inventory Risk panel.
              </div>
            )}
          </>
        ) : regime === CUSTOM_REGIME_KEY ? (
          <span className="italic">
            You have edited a control after selecting a preset. Pick a regime above to re-bundle, or keep tuning manually.
          </span>
        ) : (
          <span className="italic">Hover a regime in the dropdown to preview.</span>
        )}
      </div>
    </div>
  );
}
