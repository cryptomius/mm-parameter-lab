import { memo } from "react";
import { useChartStore } from "../state/chartStore";

const ROWS_PER_SIDE = 11;

function OrderBookLadderImpl() {
  const snap = useChartStore((s) => s.snapshot);
  if (!snap) return <div className="panel p-3 text-sub text-xs">No book yet.</div>;

  const asks = snap.asks.slice(0, ROWS_PER_SIDE);
  const bids = snap.bids.slice(0, ROWS_PER_SIDE);
  // asks: sort ascending then reverse so highest price is at the top
  const asksDisplay = [...asks].sort((a, b) => a.price - b.price).reverse();
  const bidsDisplay = [...bids].sort((a, b) => b.price - a.price);

  const maxSize = Math.max(
    1,
    ...asksDisplay.map((a) => a.size),
    ...bidsDisplay.map((b) => b.size),
  );

  const bestAsk = asksDisplay[asksDisplay.length - 1]?.price;
  const bestBid = bidsDisplay[0]?.price;
  const spread = bestAsk != null && bestBid != null ? bestAsk - bestBid : 0;
  const spreadPct = bestAsk != null && bestBid != null && snap.mid > 0
    ? (spread / snap.mid) * 100
    : 0;

  return (
    <div className="panel p-3">
      <div className="label mb-2">Order Book</div>
      <div className="grid grid-cols-[1fr_auto] text-[10px] text-sub uppercase tracking-wider mb-1 px-1">
        <span>Price</span>
        <span className="text-right">Total</span>
      </div>
      <div className="font-mono">
        {asksDisplay.map((a, i) => (
          <Row key={`a${i}`} side="ask" price={a.price} size={a.size} maxSize={maxSize} />
        ))}
        <div className="my-1 py-1 px-2 bg-bg/60 border-y border-border text-[10px] text-sub flex justify-center gap-3">
          <span>Spread:</span>
          <span className="text-ink">{spread.toFixed(4)}</span>
          <span>({spreadPct.toFixed(3)}%)</span>
        </div>
        {bidsDisplay.map((b, i) => (
          <Row key={`b${i}`} side="bid" price={b.price} size={b.size} maxSize={maxSize} />
        ))}
      </div>
    </div>
  );
}

export const OrderBookLadder = memo(OrderBookLadderImpl);

function Row({
  side,
  price,
  size,
  maxSize,
}: {
  side: "bid" | "ask";
  price: number;
  size: number;
  maxSize: number;
}) {
  const pct = (size / maxSize) * 100;
  const barColor = side === "bid" ? "bg-ask/15" : "bg-bid/15";
  const priceColor = side === "bid" ? "text-ask" : "text-bid";
  return (
    <div className="relative flex justify-between items-center py-0.5 px-1 text-[11px]">
      <div
        className={`absolute inset-y-0 right-0 ${barColor}`}
        style={{ width: `${pct}%` }}
      />
      <span className={`relative z-10 ${priceColor}`}>{price.toFixed(4)}</span>
      <span className="relative z-10 text-ink">{size.toFixed(2)}</span>
    </div>
  );
}
