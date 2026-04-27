import { memo, useEffect, useRef } from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useChartStore, type ChartTick } from "../state/chartStore";

const BUCKET_SECONDS = 5;
const UP = "#46c986";
const DOWN = "#e34d4d";

interface Candle {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  vol: number;
  isUp: boolean;
}

function bucketize(ticks: ChartTick[]): Candle[] {
  if (ticks.length === 0) return [];
  const out: Candle[] = [];
  let cur:
    | {
        bucket: number;
        open: number;
        high: number;
        low: number;
        close: number;
        firstFills: number;
        lastFills: number;
      }
    | null = null;
  for (const t of ticks) {
    if (t.mid == null || isNaN(t.mid) || t.mid === 0) continue;
    const b = Math.floor(t.t / BUCKET_SECONDS) * BUCKET_SECONDS;
    if (!cur || cur.bucket !== b) {
      if (cur) {
        out.push({
          time: cur.bucket as UTCTimestamp,
          open: cur.open,
          high: cur.high,
          low: cur.low,
          close: cur.close,
          vol: Math.max(0, cur.lastFills - cur.firstFills),
          isUp: cur.close >= cur.open,
        });
      }
      cur = {
        bucket: b,
        open: t.mid,
        high: t.mid,
        low: t.mid,
        close: t.mid,
        firstFills: t.fills_count,
        lastFills: t.fills_count,
      };
    } else {
      cur.high = Math.max(cur.high, t.mid);
      cur.low = Math.min(cur.low, t.mid);
      cur.close = t.mid;
      cur.lastFills = t.fills_count;
    }
  }
  if (cur) {
    out.push({
      time: cur.bucket as UTCTimestamp,
      open: cur.open,
      high: cur.high,
      low: cur.low,
      close: cur.close,
      vol: Math.max(0, cur.lastFills - cur.firstFills),
      isUp: cur.close >= cur.open,
    });
  }
  return out;
}

function PriceVolumeChartImpl() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Set up chart once
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      layout: {
        background: { color: "#14181d" },
        textColor: "#8a96a0",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "#1f262d" },
        horzLines: { color: "#1f262d" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        tickMarkFormatter: (t: number) => `${t}s`,
        borderColor: "#1f262d",
      },
      rightPriceScale: { borderColor: "#1f262d" },
      autoSize: true,
    });
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "transparent",
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candleSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.3 },
    });
    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.75, bottom: 0 },
    });
    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volSeriesRef.current = volSeries;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volSeriesRef.current = null;
    };
  }, []);

  // Subscribe to ticks; rebucketize and push to series
  useEffect(() => {
    const apply = (ticks: ChartTick[]) => {
      const candleSeries = candleSeriesRef.current;
      const volSeries = volSeriesRef.current;
      if (!candleSeries || !volSeries) return;
      const candles = bucketize(ticks);
      candleSeries.setData(
        candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })),
      );
      volSeries.setData(
        candles.map((c) => ({ time: c.time, value: c.vol, color: (c.isUp ? UP : DOWN) + "55" })),
      );
    };
    apply(useChartStore.getState().ticks);
    return useChartStore.subscribe((s) => apply(s.ticks));
  }, []);

  return (
    <div className="panel p-3">
      <div className="label mb-1">
        Price &amp; Volume <span className="text-sub">({BUCKET_SECONDS}s candles)</span>
      </div>
      <div ref={containerRef} className="h-64" />
    </div>
  );
}

export const PriceVolumeChart = memo(PriceVolumeChartImpl);
