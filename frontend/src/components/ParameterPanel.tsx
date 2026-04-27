import { useEffect, useRef, useState } from "react";
import { api } from "../api/rest";
import { useChartStore } from "../state/chartStore";
import { useSessionStore } from "../state/sessionStore";

export function ParameterPanel() {
  const gamma = useSessionStore((s) => s.state.gamma);
  const k = useSessionStore((s) => s.state.k);
  const tau = useSessionStore((s) => s.state.tau);
  const running = useSessionStore((s) => s.state.running);
  const readLastT = () => {
    const ticks = useChartStore.getState().ticks;
    return ticks.length ? ticks[ticks.length - 1].t : undefined;
  };
  return (
    <div className="panel p-3">
      <div className="label mb-2">Quoter Parameters</div>
      <Field
        label="γ (inv aversion)"
        serverValue={gamma}
        onCommit={(v) => api.patchParams({ gamma: v })}
        readCurrentT={readLastT}
        disabled={!running}
      />
      <Field
        label="k (rent slope)"
        serverValue={k}
        onCommit={(v) => api.patchParams({ k: v })}
        readCurrentT={readLastT}
        disabled={!running}
      />
      <Field
        label="τ (lookback s)"
        serverValue={tau}
        onCommit={(v) => api.patchParams({ tau: v })}
        readCurrentT={readLastT}
        disabled={!running}
      />
      <div className="text-[10px] text-sub mt-2">Press Enter or blur to apply.</div>
    </div>
  );
}

function Field({
  label,
  serverValue,
  onCommit,
  readCurrentT,
  disabled,
}: {
  label: string;
  serverValue: number | undefined;
  onCommit: (v: number) => Promise<unknown>;
  readCurrentT: () => number | undefined;
  disabled: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);
  const [appliedAt, setAppliedAt] = useState<number | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (!dirtyRef.current && serverValue != null && inputRef.current) {
      inputRef.current.value = String(serverValue);
    }
  }, [serverValue]);

  const commit = async () => {
    const raw = inputRef.current?.value ?? "";
    const n = Number(raw);
    dirtyRef.current = false;
    setIsDirty(false);
    if (isNaN(n) || n === serverValue) return;
    await onCommit(n);
    setAppliedAt(readCurrentT() ?? 0);
  };

  return (
    <div className="flex justify-between items-center mb-2 gap-2">
      <span className="text-xs text-sub whitespace-nowrap">{label}</span>
      <div className="flex flex-col items-end flex-1">
        <input
          ref={inputRef}
          className={`input ${isDirty ? "ring-1 ring-warn" : ""}`}
          defaultValue={serverValue != null ? String(serverValue) : ""}
          disabled={disabled}
          onChange={() => {
            dirtyRef.current = true;
            setIsDirty(true);
          }}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
        />
        {appliedAt != null && (
          <span className="text-[9px] text-ask mt-0.5">✓ applied at t={appliedAt.toFixed(1)}s</span>
        )}
      </div>
    </div>
  );
}
