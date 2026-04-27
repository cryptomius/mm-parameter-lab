import { create } from "zustand";
import type { Experiment, L2Snapshot, SessionState } from "../types/messages";

interface QuoteTick {
  t: number;
  inventory: number;
  total_pnl: number;
  spread_pnl: number;
  inventory_pnl: number;
  sigma_est: number;
  active_interventions: string[];
}

interface Store {
  experiments: Experiment[];
  selectedId: string;
  setSelected: (id: string) => void;
  state: SessionState;
  setState: (s: SessionState) => void;
  ticks: QuoteTick[];
  pushTick: (t: QuoteTick) => void;
  snapshot: L2Snapshot | null;
  setSnapshot: (s: L2Snapshot) => void;
  loadExperiments: () => Promise<void>;
}

const MAX_TICKS = 600; // ~ last 1 min at 10Hz

export const useSessionStore = create<Store>((set, get) => ({
  experiments: [],
  selectedId: "baseline_calm",
  setSelected: (id) => set({ selectedId: id }),
  state: { running: false },
  setState: (s) => set({ state: s }),
  ticks: [],
  pushTick: (t) => {
    const arr = [...get().ticks, t];
    if (arr.length > MAX_TICKS) arr.splice(0, arr.length - MAX_TICKS);
    set({ ticks: arr });
  },
  snapshot: null,
  setSnapshot: (s) => set({ snapshot: s }),
  loadExperiments: async () => {
    const r = await fetch("/api/experiments");
    const xs = (await r.json()) as Experiment[];
    set({ experiments: xs, selectedId: xs[0]?.id ?? "baseline_calm" });
  },
}));
