import type { Experiment, SessionState } from "../types/messages";

const j = async (r: Response) => {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

export const api = {
  experiments: () => fetch("/api/experiments").then(j) as Promise<Experiment[]>,
  state: () => fetch("/api/session/state").then(j) as Promise<SessionState>,
  start: (experimentId: string, speed = 5) =>
    fetch("/api/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ experiment_id: experimentId, speed }),
    }).then(j),
  stop: () => fetch("/api/session/stop", { method: "POST" }).then(j),
  pause: (paused: boolean) =>
    fetch("/api/session/pause", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused }),
    }).then(j),
  patchParams: (patch: Record<string, number>) =>
    fetch("/api/session/parameters", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j),
  patchIntervention: (name: string, enabled: boolean) =>
    fetch("/api/session/interventions", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, enabled }),
    }).then(j),
  patchInterventionParams: (patch: Record<string, number>) =>
    fetch("/api/session/intervention_params", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(j),
  inject: (kind: string, params: Record<string, unknown> = {}) =>
    fetch("/api/session/inject_event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, params }),
    }).then(j),
};
