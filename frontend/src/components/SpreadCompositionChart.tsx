import { memo, useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { useChartStore, type ChartTick } from "../state/chartStore";

// Two AS half-spread components on independent y-axes:
//   left  axis = rent  = (1/γ)·ln(1+γ/k)   — usually large & near-constant
//   right axis = inv_risk = γ·σ²·τ/2       — usually tiny but vol-driven
// Independent scales let each component's variation be visible regardless
// of magnitude, instead of being swamped on a shared axis.
function build(ticks: ChartTick[]): uPlot.AlignedData {
  const n = ticks.length;
  const x = new Float64Array(n);
  const rent = new Float64Array(n);
  const inv = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = ticks[i].t;
    rent[i] = ticks[i].rent_term;
    inv[i] = ticks[i].inv_risk_term;
  }
  return [
    x as unknown as number[],
    rent as unknown as number[],
    inv as unknown as number[],
  ];
}

function SpreadCompositionChartImpl() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const opts: uPlot.Options = {
      width: el.clientWidth || 600,
      height: el.clientHeight || 160,
      pxAlign: 0,
      cursor: { drag: { x: false, y: false } },
      legend: { show: true, live: false },
      scales: {
        x: { time: false },
        rent: { auto: true },
        invrisk: { auto: true },
      },
      axes: [
        { stroke: "#8a96a0", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", values: (_u, ticks) => ticks.map((t) => `${t.toFixed(0)}s`) },
        { scale: "rent", stroke: "#e6b15e", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", size: 60 },
        { scale: "invrisk", side: 1, stroke: "#46c986", grid: { show: false }, ticks: { stroke: "#1f262d" }, font: "10px monospace", size: 70, values: (_u, ticks) => ticks.map((t) => t.toExponential(1)) },
      ],
      series: [
        {},
        { label: "rent (left axis)", scale: "rent", stroke: "#e6b15e", width: 1.5, points: { show: false } },
        { label: "inv_risk (right axis)", scale: "invrisk", stroke: "#46c986", width: 1.5, points: { show: false } },
      ],
    };
    const u = new uPlot(opts, build([]), el);
    chartRef.current = u;
    const ro = new ResizeObserver(() => {
      if (chartRef.current && el) {
        chartRef.current.setSize({ width: el.clientWidth, height: el.clientHeight });
      }
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      u.destroy();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const apply = (ticks: ChartTick[]) => {
      chartRef.current?.setData(build(ticks));
    };
    apply(useChartStore.getState().ticks);
    return useChartStore.subscribe((s) => apply(s.ticks));
  }, []);

  return (
    <div className="panel p-3 h-full flex flex-col">
      <div className="label mb-1 flex-shrink-0">
        Half-Spread Composition (AS) — rent = (1/γ)·ln(1+γ/k) [left], inv_risk = γ·σ²·τ/2 [right]
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}

export const SpreadCompositionChart = memo(SpreadCompositionChartImpl);
