import { useSessionStore } from "../state/sessionStore";

export function OrderBookLadder() {
  const snap = useSessionStore((s) => s.snapshot);
  if (!snap) return <div className="panel p-3 text-sub text-xs">No book yet.</div>;
  const maxSz = Math.max(
    ...snap.bids.map((b) => b.size),
    ...snap.asks.map((a) => a.size),
    1,
  );
  return (
    <div className="panel p-3">
      <div className="label mb-2">Order Book — mid {snap.mid.toFixed(4)}</div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-[10px] text-bid mb-1">BIDS</div>
          {snap.bids.slice(0, 10).map((b, i) => (
            <Row key={`b${i}`} side="bid" price={b.price} size={b.size} maxSize={maxSz} />
          ))}
        </div>
        <div>
          <div className="text-[10px] text-ask mb-1">ASKS</div>
          {snap.asks.slice(0, 10).map((a, i) => (
            <Row key={`a${i}`} side="ask" price={a.price} size={a.size} maxSize={maxSz} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({ side, price, size, maxSize }: { side: "bid" | "ask"; price: number; size: number; maxSize: number }) {
  const pct = (size / maxSize) * 100;
  const color = side === "bid" ? "bg-bid/20" : "bg-ask/20";
  return (
    <div className="relative text-xs flex justify-between py-0.5">
      <div className={`absolute inset-0 ${color}`} style={{ width: `${pct}%` }} />
      <span className="relative z-10">{price.toFixed(4)}</span>
      <span className="relative z-10 text-sub">{size.toFixed(2)}</span>
    </div>
  );
}
