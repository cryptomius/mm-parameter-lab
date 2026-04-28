import { create } from "zustand";
import { api } from "../api/rest";
import { CUSTOM_REGIME_KEY, findRegime } from "./regimes";
import type { Experiment, InterventionEventPayload, ScenarioEventPayload, SessionState } from "../types/messages";

export type EventLogEntry = (
  | ({ category: "scenario" } & ScenarioEventPayload)
  | ({ category: "intervention" } & InterventionEventPayload)
) & { id: number };

interface Store {
  experiments: Experiment[];
  selectedId: string;
  setSelected: (id: string) => void;
  state: SessionState;
  setState: (s: SessionState) => void;
  patchInterventionLocal: (name: string, enabled: boolean) => void;
  events: EventLogEntry[];
  pushEvent: (e: ScenarioEventPayload) => void;
  pushIntervention: (e: InterventionEventPayload) => void;
  resetEvents: () => void;
  loadExperiments: () => Promise<void>;
  // Operating regime (preset of params + intervention flags). Editing any
  // individual control switches this to "custom" so the dropdown reflects
  // divergence from the preset.
  regime: string;
  setRegime: (key: string) => void;
  applyRegime: (key: string) => Promise<void>;
}

const MAX_EVENTS = 50;
let _eventSeq = 0;

export const useSessionStore = create<Store>((set, get) => ({
  experiments: [],
  selectedId: "baseline_calm",
  setSelected: (id) => set({ selectedId: id }),
  state: { running: false },
  setState: (s) => set({ state: s }),
  patchInterventionLocal: (name, enabled) =>
    set((st) => ({
      state: {
        ...st.state,
        interventions: { ...(st.state.interventions ?? {}), [name]: enabled },
      },
    })),
  events: [],
  pushEvent: (e) => {
    _eventSeq += 1;
    const arr: EventLogEntry[] = [
      { category: "scenario", ...e, id: _eventSeq },
      ...get().events,
    ];
    if (arr.length > MAX_EVENTS) arr.length = MAX_EVENTS;
    set({ events: arr });
  },
  pushIntervention: (e) => {
    _eventSeq += 1;
    const arr: EventLogEntry[] = [
      { category: "intervention", ...e, id: _eventSeq },
      ...get().events,
    ];
    if (arr.length > MAX_EVENTS) arr.length = MAX_EVENTS;
    set({ events: arr });
  },
  resetEvents: () => set({ events: [] }),
  loadExperiments: async () => {
    const r = await fetch("/api/experiments");
    const xs = (await r.json()) as Experiment[];
    set({ experiments: xs, selectedId: xs[0]?.id ?? "baseline_calm" });
  },
  regime: "calm_spread_capture",
  setRegime: (key) => set({ regime: key }),
  applyRegime: async (key) => {
    const regime = findRegime(key);
    if (!regime) return;
    // Optimistic local update so the dropdown + info box don't blink to
    // "custom" while the PATCHes are in flight.
    set({ regime: key });
    // Patch parameters and intervention flags in parallel.
    const tasks: Promise<unknown>[] = [api.patchParams(regime.params)];
    for (const [name, enabled] of Object.entries(regime.interventions)) {
      tasks.push(api.patchIntervention(name, enabled));
    }
    try {
      await Promise.all(tasks);
      // Refetch authoritative state so the UI reflects the new bundle.
      const fresh = await api.state();
      set({ state: fresh });
    } catch (err) {
      // On any failure, revert dropdown to "custom" to flag divergence.
      set({ regime: CUSTOM_REGIME_KEY });
      throw err;
    }
  },
}));
