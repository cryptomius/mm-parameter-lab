import { memo, useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { useChartStore, type ChartTick } from "../state/chartStore";

function build(ticks: ChartTick[]): uPlot.AlignedData {
  const n = ticks.length;
  const x = new Float64Array(n);
  const spread = new Float64Array(n);
  const inv = new Float64Array(n);
  const total = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = ticks[i].t;
    spread[i] = ticks[i].spread_pnl;
    inv[i] = ticks[i].inventory_pnl;
    total[i] = ticks[i].total_pnl;
  }
  return [
    x as unknown as number[],
    spread as unknown as number[],
    inv as unknown as number[],
    total as unknown as number[],
  ];
}

function PnLChartImpl() {
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
      scales: { x: { time: false } },
      axes: [
        { stroke: "#8a96a0", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", values: (_u, ticks) => ticks.map((t) => `${t.toFixed(0)}s`) },
        { stroke: "#8a96a0", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", size: 50 },
      ],
      series: [
        {},
        { label: "spread", stroke: "#46c986", width: 1, points: { show: false } },
        { label: "inventory", stroke: "#e6b15e", width: 1, points: { show: false } },
        { label: "total", stroke: "#e7ecf0", width: 2, points: { show: false } },
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
      <div className="label mb-1 flex-shrink-0">PnL Decomposition</div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}

export const PnLChart = memo(PnLChartImpl);
