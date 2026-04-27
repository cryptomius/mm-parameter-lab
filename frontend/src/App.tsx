import { useEffect } from "react";
import { api } from "./api/rest";
import { wsClient } from "./api/ws";
import { InventoryChart } from "./components/InventoryChart";
import { InterventionToggles } from "./components/InterventionToggles";
import { MetricsDashboard } from "./components/MetricsDashboard";
import { OrderBookLadder } from "./components/OrderBookLadder";
import { ParameterPanel } from "./components/ParameterPanel";
import { PnLChart } from "./components/PnLChart";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { useSessionStore } from "./state/sessionStore";
import type { L2Snapshot } from "./types/messages";

export default function App() {
  const { experiments, selectedId, setSelected, state, setState, pushTick, setSnapshot, loadExperiments } =
    useSessionStore();

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const s = await api.state();
        setState(s);
      } catch {
        /* ignore */
      }
    }, 1000);
    return () => clearInterval(id);
  }, [setState]);

  useEffect(() => {
    if (!state.running) return;
    wsClient.connect();
    const off = wsClient.subscribe((msg) => {
      if (msg.kind === "quote_update") {
        const p = msg.payload as Record<string, number | string[]>;
        pushTick({
          t: Number(p.t),
          inventory: Number(p.inventory),
          total_pnl: Number(p.total_pnl),
          spread_pnl: Number(p.spread_pnl),
          inventory_pnl: Number(p.inventory_pnl),
          sigma_est: Number(p.sigma_est),
          active_interventions: (p.active_interventions as string[]) ?? [],
        });
      } else if (msg.kind === "snapshot") {
        setSnapshot(msg.payload as unknown as L2Snapshot);
      }
    });
    return () => {
      off();
      wsClient.disconnect();
    };
  }, [state.running, pushTick, setSnapshot]);

  const onStart = async () => {
    await api.start(selectedId, 5);
    const s = await api.state();
    setState(s);
  };
  const onStop = async () => {
    await api.stop();
    setState({ running: false });
  };

  return (
    <div className="min-h-screen p-3">
      <header className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">MM Sim</h1>
          <select
            className="input w-56"
            value={selectedId}
            onChange={(e) => setSelected(e.target.value)}
            disabled={state.running}
          >
            {experiments.map((e) => (
              <option key={e.id} value={e.id}>
                [{e.finding}] {e.id}
              </option>
            ))}
          </select>
          {!state.running ? (
            <button className="btn-primary" onClick={onStart}>▶ Start</button>
          ) : (
            <button className="btn-danger" onClick={onStop}>■ Stop</button>
          )}
          <span className="text-xs text-sub">
            {state.running ? `running ${state.experiment_id} · t=${(state.sim_t ?? 0).toFixed(1)}s` : "idle"}
          </span>
        </div>
      </header>

      <main className="grid grid-cols-12 gap-3">
        <section className="col-span-3">
          <OrderBookLadder />
        </section>
        <section className="col-span-6 space-y-3">
          <InventoryChart />
          <PnLChart />
        </section>
        <section className="col-span-3 space-y-3">
          <MetricsDashboard />
          <ParameterPanel />
          <InterventionToggles />
          <ScenarioPanel />
        </section>
      </main>
    </div>
  );
}
