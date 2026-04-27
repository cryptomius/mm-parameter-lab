import { create } from "zustand";
import type { FillPayload, L2Snapshot } from "../types/messages";

export interface ChartTick {
  t: number;
  mid: number;
  fills_count: number;
  inventory: number;
  total_pnl: number;
  spread_pnl: number;
  inventory_pnl: number;
  sigma_est: number;
  active_interventions: string[];
}

export type ChartFill = FillPayload & { id: number };

interface ChartStore {
  ticks: ChartTick[];
  fills: ChartFill[];
  snapshot: L2Snapshot | null;
  appendTicks: (ts: ChartTick[]) => void;
  appendFills: (fs: FillPayload[]) => void;
  setSnapshot: (s: L2Snapshot) => void;
  reset: () => void;
}

const MAX_TICKS = 1200;
const MAX_FILLS = 100;
let _fillSeq = 0;

export const useChartStore = create<ChartStore>((set, get) => ({
  ticks: [],
  fills: [],
  snapshot: null,
  appendTicks: (ts) => {
    if (ts.length === 0) return;
    const arr = get().ticks.concat(ts);
    if (arr.length > MAX_TICKS) arr.splice(0, arr.length - MAX_TICKS);
    set({ ticks: arr });
  },
  appendFills: (fs) => {
    if (fs.length === 0) return;
    const tagged: ChartFill[] = fs.map((f) => ({ ...f, id: ++_fillSeq }));
    // Newest first; cap at MAX_FILLS
    const arr = tagged.reverse().concat(get().fills);
    if (arr.length > MAX_FILLS) arr.length = MAX_FILLS;
    set({ fills: arr });
  },
  setSnapshot: (s) => set({ snapshot: s }),
  reset: () => set({ ticks: [], fills: [], snapshot: null }),
}));
