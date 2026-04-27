import { useState } from "react";
import { api } from "../api/rest";
import { useSessionStore } from "../state/sessionStore";

export function ParameterPanel() {
  const state = useSessionStore((s) => s.state);
  const [gamma, setGamma] = useState<string>(String(state.gamma ?? 0.1));
  const [k, setK] = useState<string>(String(state.k ?? 10));
  const [tau, setTau] = useState<string>(String(state.tau ?? 300));

  const apply = async (patch: Record<string, number>) => {
    await api.patchParams(patch);
  };

  return (
    <div className="panel p-3">
      <div className="label mb-2">Quoter Parameters</div>
      <Field
        label="γ (inv aversion)"
        value={gamma}
        onChange={setGamma}
        onCommit={(v) => apply({ gamma: v })}
      />
      <Field label="k (rent slope)" value={k} onChange={setK} onCommit={(v) => apply({ k: v })} />
      <Field label="τ (lookback s)" value={tau} onChange={setTau} onCommit={(v) => apply({ tau: v })} />
      <div className="text-[10px] text-sub mt-2">Edits apply to next quote refresh.</div>
    </div>
  );
}

function Field({
  label, value, onChange, onCommit,
}: { label: string; value: string; onChange: (v: string) => void; onCommit: (v: number) => void }) {
  return (
    <div className="flex justify-between items-center mb-2">
      <span className="text-xs text-sub">{label}</span>
      <input
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => {
          const n = Number(value);
          if (!isNaN(n)) onCommit(n);
        }}
      />
    </div>
  );
}
