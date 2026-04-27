import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { useSessionStore } from "../state/sessionStore";

export function InventoryChart() {
  const ticks = useSessionStore((s) => s.ticks);
  const limit = 100;
  const data = ticks.map((t) => ({ t: t.t.toFixed(1), inv: t.inventory }));
  return (
    <div className="panel p-3 h-48">
      <div className="label mb-1">Inventory</div>
      <ResponsiveContainer width="100%" height="90%">
        <AreaChart data={data}>
          <XAxis dataKey="t" hide />
          <YAxis domain={[-limit, limit]} fontSize={10} stroke="#8a96a0" />
          <Tooltip contentStyle={{ background: "#14181d", border: "1px solid #1f262d" }} />
          <ReferenceLine y={0} stroke="#8a96a0" />
          <ReferenceLine y={limit} stroke="#e34d4d" strokeDasharray="3 3" />
          <ReferenceLine y={-limit} stroke="#e34d4d" strokeDasharray="3 3" />
          <Area type="monotone" dataKey="inv" stroke="#46c986" fill="#46c986" fillOpacity={0.18} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
