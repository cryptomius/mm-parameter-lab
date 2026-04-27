import { useEffect } from "react";
import { api } from "./api/rest";
import { startWsPump, stopWsPump } from "./api/wsPump";
import { InventoryChart } from "./components/InventoryChart";
import { InterventionToggles } from "./components/InterventionToggles";
import { MetricsDashboard } from "./components/MetricsDashboard";
import { OrderBookLadder } from "./components/OrderBookLadder";
import { ParameterPanel } from "./components/ParameterPanel";
import { PnLChart } from "./components/PnLChart";
import { PriceVolumeChart } from "./components/PriceVolumeChart";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { TradesTape } from "./components/TradesTape";
import { useChartStore } from "./state/chartStore";
import { useSessionStore } from "./state/sessionStore";

export default function App() {
  const experiments = useSessionStore((s) => s.experiments);
  const selectedId = useSessionStore((s) => s.selectedId);
  const setSelected = useSessionStore((s) => s.setSelected);
  const running = useSessionStore((s) => s.state.running);
  const experimentId = useSessionStore((s) => s.state.experiment_id);
  const simT = useSessionStore((s) => s.state.sim_t);
  const setState = useSessionStore((s) => s.setState);
  const resetEvents = useSessionStore((s) => s.resetEvents);
  const loadExperiments = useSessionStore((s) => s.loadExperiments);
  const viewAll = useChartStore((s) => s.viewAll);
  const setViewAll = useChartStore((s) => s.setViewAll);

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  // Poll session state at 1 Hz; reset chart + events when sim ends naturally
  useEffect(() => {
    let prev: boolean | null = null;
    const id = setInterval(async () => {
      try {
        const s = await api.state();
        if (prev === true && s.running === false) {
          useChartStore.getState().reset();
          resetEvents();
        }
        prev = s.running;
        setState(s);
      } catch {
        /* ignore */
      }
    }, 1000);
    return () => clearInterval(id);
  }, [setState, resetEvents]);

  // Start/stop the WS pump as a side-effect of session state — runs off the
  // React render path and feeds the chart store at 10 Hz max.
  useEffect(() => {
    if (!running) return;
    startWsPump();
    return () => stopWsPump();
  }, [running]);

  const onStart = async () => {
    useChartStore.getState().reset();
    resetEvents();
    await api.start(selectedId, 5);
    const s = await api.state();
    setState(s);
  };
  const onStop = async () => {
    await api.stop();
    setState({ running: false });
    useChartStore.getState().reset();
    resetEvents();
  };

  return (
    <div className="h-screen flex flex-col p-3">
      <header className="flex justify-between items-center mb-3 flex-shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">MM Sim</h1>
          <select
            className="input w-56"
            value={selectedId}
            onChange={(e) => setSelected(e.target.value)}
            disabled={running}
          >
            {experiments.map((e) => (
              <option key={e.id} value={e.id}>
                [{e.finding}] {e.id}
              </option>
            ))}
          </select>
          {!running ? (
            <button className="btn-primary" onClick={onStart}>▶ Start</button>
          ) : (
            <button className="btn-danger" onClick={onStop}>■ Stop</button>
          )}
          <span className="text-xs text-sub">
            {running ? `running ${experimentId} · t=${(simT ?? 0).toFixed(1)}s` : "idle"}
          </span>
          <label
            className="ml-2 flex items-center gap-1 text-xs text-sub cursor-pointer"
            title="Keep up to 60 minutes of chart history instead of 6. Enable before Start to capture from t=0."
          >
            <input
              type="checkbox"
              checked={viewAll}
              onChange={(e) => setViewAll(e.target.checked)}
            />
            view all
          </label>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-12 gap-3 min-h-0">
        <section className="col-span-3 flex flex-col gap-3 min-h-0 overflow-hidden">
          <OrderBookLadder />
          <TradesTape />
        </section>
        <section className="col-span-6 flex flex-col gap-3 min-h-0">
          <div className="flex-1 min-h-0">
            <PriceVolumeChart />
          </div>
          <div className="flex-1 min-h-0">
            <InventoryChart />
          </div>
          <div className="flex-1 min-h-0">
            <PnLChart />
          </div>
        </section>
        <section className="col-span-3 flex flex-col gap-3 min-h-0 overflow-y-auto">
          <MetricsDashboard />
          <ParameterPanel />
          <InterventionToggles />
          <ScenarioPanel />
        </section>
      </main>
    </div>
  );
}
