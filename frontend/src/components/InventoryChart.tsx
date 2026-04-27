import { memo, useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { useChartStore, type ChartTick } from "../state/chartStore";

const LIMIT = 100;

function build(ticks: ChartTick[]): uPlot.AlignedData {
  const x = new Float64Array(ticks.length);
  const y = new Float64Array(ticks.length);
  for (let i = 0; i < ticks.length; i++) {
    x[i] = ticks[i].t;
    y[i] = ticks[i].inventory;
  }
  return [x as unknown as number[], y as unknown as number[]];
}

function InventoryChartImpl() {
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
      legend: { show: false },
      scales: {
        x: { time: false },
        y: { range: [-LIMIT * 1.1, LIMIT * 1.1] },
      },
      axes: [
        { stroke: "#8a96a0", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", values: (_u, ticks) => ticks.map((t) => `${t.toFixed(0)}s`) },
        { stroke: "#8a96a0", grid: { stroke: "#1f262d22" }, ticks: { stroke: "#1f262d" }, font: "10px monospace", size: 40 },
      ],
      series: [
        {},
        {
          stroke: "#46c986",
          fill: "#46c98622",
          width: 1.5,
          points: { show: false },
        },
      ],
      hooks: {
        draw: [
          (u) => {
            const { ctx } = u;
            const yScale = u.scales.y;
            if (yScale.min == null || yScale.max == null) return;
            ctx.save();
            ctx.strokeStyle = "#e34d4d";
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            const yp = u.valToPos(LIMIT, "y", true);
            const yn = u.valToPos(-LIMIT, "y", true);
            ctx.moveTo(u.bbox.left, yp); ctx.lineTo(u.bbox.left + u.bbox.width, yp);
            ctx.moveTo(u.bbox.left, yn); ctx.lineTo(u.bbox.left + u.bbox.width, yn);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.strokeStyle = "#8a96a0";
            ctx.beginPath();
            const y0 = u.valToPos(0, "y", true);
            ctx.moveTo(u.bbox.left, y0); ctx.lineTo(u.bbox.left + u.bbox.width, y0);
            ctx.stroke();
            ctx.restore();
          },
        ],
      },
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
    <div className="panel p-3 h-48 flex flex-col">
      <div className="label mb-1">Inventory</div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}

export const InventoryChart = memo(InventoryChartImpl);
