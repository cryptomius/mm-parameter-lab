import { api } from "../api/rest";

const EVENTS = [
  { kind: "selloff", label: "Sell-off", params: { size: 60 } },
  { kind: "buyin", label: "Buy-in", params: { size: 60 } },
  { kind: "newsspike", label: "News spike", params: { log_jump: 0.015, sigma_mult: 4, vol_duration_s: 90 } },
  { kind: "liqwithdraw", label: "Liquidity withdrawal", params: { multiplier: 0.2, duration_s: 600 } },
  { kind: "toxicburst", label: "Toxic burst", params: { multiplier: 8, duration_s: 120 } },
];

export function ScenarioPanel() {
  return (
    <div className="panel p-3">
      <div className="label mb-2">Inject Scenario</div>
      <div className="grid grid-cols-2 gap-1">
        {EVENTS.map((ev) => (
          <button
            key={ev.kind}
            className="btn text-left"
            onClick={() => api.inject(ev.kind, ev.params)}
          >
            {ev.label}
          </button>
        ))}
      </div>
    </div>
  );
}
