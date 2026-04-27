import { memo } from "react";
import { useChartStore } from "../state/chartStore";

const fmtT = (t: number) => {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const ms = Math.floor((t - Math.floor(t)) * 10);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${ms}`;
};

function TradesTapeImpl() {
  const fills = useChartStore((s) => s.fills);
  return (
    <div className="panel p-3">
      <div className="label mb-2">Market Trades</div>
      <div className="grid grid-cols-[14px_1fr_1fr_auto] text-[10px] text-sub uppercase tracking-wider mb-1 px-1">
        <span></span>
        <span>Price</span>
        <span className="text-right">Quantity</span>
        <span className="text-right pl-2">Time</span>
      </div>
      <div className="font-mono max-h-[420px] overflow-y-auto">
        {fills.length === 0 && <div className="text-sub text-xs px-1 py-2">No trades yet.</div>}
        {fills.map((f) => {
          const isBuy = f.aggressor === "buy";
          const color = isBuy ? "text-ask" : "text-bid";
          const arrow = isBuy ? "▲" : "▼";
          return (
            <div
              key={f.id}
              className={`grid grid-cols-[14px_1fr_1fr_auto] items-center px-1 py-0.5 text-[11px] ${color} ${
                f.mm ? "bg-warn/5" : ""
              }`}
              title={f.mm ? "MM-involved fill" : "External-only fill"}
            >
              <span className="text-[9px]">{arrow}</span>
              <span>{f.price.toFixed(4)}</span>
              <span className="text-right">{f.size.toFixed(2)}</span>
              <span className="text-right pl-2 text-sub">{fmtT(f.t)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const TradesTape = memo(TradesTapeImpl);
