import { api } from "../api/rest";
import { useSessionStore } from "../state/sessionStore";

const NAMES: { name: string; label: string }[] = [
  { name: "adaptive_spread", label: "Adaptive spread" },
  { name: "kill_switch", label: "Kill switch" },
  { name: "news_detector", label: "News detector" },
  { name: "hedge_on_threshold", label: "Hedge on threshold" },
  { name: "per_counterparty_penalty", label: "Per-CP penalty" },
];

export function InterventionToggles() {
  const intr = useSessionStore((s) => s.state.interventions ?? {});
  return (
    <div className="panel p-3">
      <div className="label mb-2">Interventions</div>
      {NAMES.map((it) => (
        <label key={it.name} className="flex items-center justify-between text-xs py-1">
          <span>{it.label}</span>
          <input
            type="checkbox"
            checked={!!intr[it.name]}
            onChange={(e) => api.patchIntervention(it.name, e.target.checked)}
          />
        </label>
      ))}
    </div>
  );
}
