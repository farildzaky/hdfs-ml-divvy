"use client";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";

const PALETTE = ["#6366f1", "#06b6d4", "#f59e0b", "#ec4899", "#10b981", "#8b5cf6"];
const MEMBER = "#6366f1";
const CASUAL = "#f59e0b";
const AXIS = { fontSize: 11, fill: "currentColor" };
const grid = <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.1} />;
const TIP = { background: "#0b1020", border: "none", borderRadius: 8, color: "#fff" };
const compact = (v: number) => new Intl.NumberFormat("id-ID", { notation: "compact" }).format(v);

export function BarX({ data, x, y, name, color = MEMBER, height = 260 }:
  { data: any[]; x: string; y: string; name?: string; color?: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey={x} tick={AXIS} interval={0} angle={-25} textAnchor="end" height={80} />
        <YAxis tick={AXIS} width={54} />
        <Tooltip contentStyle={TIP} />
        <Bar dataKey={y} name={name} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// member vs casual, the comparison most charts on this dashboard make
export function RiderBars({ data, x, stacked = false, height = 280 }:
  { data: any[]; x: string; stacked?: boolean; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey={x} tick={AXIS} />
        <YAxis tick={AXIS} width={54} tickFormatter={compact} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Bar dataKey="member" name="Member (berlangganan)" fill={MEMBER} stackId={stacked ? "a" : undefined} />
        <Bar dataKey="casual" name="Casual (tanpa langganan)" fill={CASUAL} stackId={stacked ? "a" : undefined} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RiderLines({ data, x, height = 280 }: { data: any[]; x: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey={x} tick={AXIS} />
        <YAxis tick={AXIS} width={54} tickFormatter={compact} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Line type="monotone" dataKey="member" name="Member (berlangganan)" stroke={MEMBER} strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="casual" name="Casual (tanpa langganan)" stroke={CASUAL} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function MonthlyTestChart({ data, height = 300 }: { data: any[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey="month" tick={AXIS} />
        <YAxis domain={[0.4, 1]} tick={AXIS} width={40} />
        <Tooltip contentStyle={TIP} />
        <Legend />
        <Line type="monotone" dataKey="accuracy" name="Akurasi model" stroke={MEMBER} strokeWidth={2} />
        <Line type="monotone" dataKey="baseline_accuracy" name="Akurasi tanpa model" stroke={CASUAL} strokeDasharray="5 4" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CurveX({ data, x, y, color = MEMBER, height = 260 }:
  { data: any[]; x: string; y: string; color?: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey={x} type="number" domain={[0, 1]} tick={AXIS} />
        <YAxis type="number" domain={[0, 1]} tick={AXIS} width={44} />
        <Tooltip contentStyle={TIP} />
        <Line type="monotone" dataKey={y} stroke={color} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// longitude/latitude scatter: a street map would need an outside tile server
export function StationMap({ points, clusters, height = 560 }:
  { points: { station: string; lat: number; lng: number; rides: number; cluster: number }[]; clusters: { cluster: number; label: string }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ left: 4, right: 12, top: 8, bottom: 8 }}>
        {grid}
        <XAxis dataKey="lng" name="Bujur" type="number" domain={["dataMin", "dataMax"]} tick={AXIS} tickFormatter={(v) => v.toFixed(2)} />
        <YAxis dataKey="lat" name="Lintang" type="number" domain={["dataMin", "dataMax"]} tick={AXIS} width={48} tickFormatter={(v) => v.toFixed(2)} />
        <ZAxis dataKey="rides" range={[12, 160]} name="Perjalanan" />
        <Tooltip contentStyle={TIP} content={({ active, payload }) => {
          const p: any = active && payload?.[0]?.payload;
          return p ? <div style={{ ...TIP, padding: 8, fontSize: 12 }}>{p.station}<br />{new Intl.NumberFormat("id-ID").format(p.rides)} perjalanan</div> : null;
        }} />
        <Legend />
        {clusters.map((c) => (
          <Scatter key={c.cluster} name={c.label} data={points.filter((p) => p.cluster === c.cluster)}
            fill={PALETTE[c.cluster % PALETTE.length]} fillOpacity={0.75} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export { PALETTE };
