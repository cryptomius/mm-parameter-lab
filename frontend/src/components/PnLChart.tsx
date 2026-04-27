import { Line, LineChart, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from "recharts";
import { useSessionStore } from "../state/sessionStore";

export function PnLChart() {
  const ticks = useSessionStore((s) => s.ticks);
  const data = ticks.map((t) => ({
    t: t.t.toFixed(1),
    spread: t.spread_pnl,
    inventory: t.inventory_pnl,
    total: t.total_pnl,
  }));
  return (
    <div className="panel p-3 h-48">
      <div className="label mb-1">PnL Decomposition</div>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={data}>
          <XAxis dataKey="t" hide />
          <YAxis fontSize={10} stroke="#8a96a0" />
          <Tooltip contentStyle={{ background: "#14181d", border: "1px solid #1f262d" }} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Line type="monotone" dataKey="spread" stroke="#46c986" dot={false} />
          <Line type="monotone" dataKey="inventory" stroke="#e6b15e" dot={false} />
          <Line type="monotone" dataKey="total" stroke="#e7ecf0" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
