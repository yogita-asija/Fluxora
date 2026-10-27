import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, PageHeader } from "../components/ui.jsx";

// Static sample data: real metrics arrive once orders flow through the system.
const SAMPLE = [
  { day: "Mon", orders: 42, revenue: 3120 },
  { day: "Tue", orders: 55, revenue: 4210 },
  { day: "Wed", orders: 48, revenue: 3760 },
  { day: "Thu", orders: 70, revenue: 5480 },
  { day: "Fri", orders: 81, revenue: 6390 },
  { day: "Sat", orders: 64, revenue: 4980 },
  { day: "Sun", orders: 39, revenue: 2870 },
];

const ACCENT = "#6366f1";

const tooltipStyle = {
  background: "var(--chart-tooltip-bg)",
  border: "1px solid var(--chart-tooltip-border)",
  borderRadius: 8,
  color: "var(--chart-tooltip-text)",
  fontSize: 12,
};

function ChartCard({ title, children }) {
  return (
    <Card className="p-5">
      <h2 className="mb-4 text-sm font-medium">{title}</h2>
      <div className="h-64 text-slate-400 dark:text-slate-500">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

const axisProps = {
  tick: { fill: "currentColor", fontSize: 12 },
  axisLine: false,
  tickLine: false,
};

export default function Analytics() {
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Revenue and order volume. Charts below use sample data."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Orders per day (sample)">
          <BarChart data={SAMPLE}>
            <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.15} />
            <XAxis dataKey="day" {...axisProps} />
            <YAxis {...axisProps} width={32} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "currentColor", fillOpacity: 0.08 }} />
            <Bar dataKey="orders" fill={ACCENT} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Revenue per day (sample)">
          <LineChart data={SAMPLE}>
            <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.15} />
            <XAxis dataKey="day" {...axisProps} />
            <YAxis {...axisProps} width={44} />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey="revenue" stroke={ACCENT} strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>
      </div>
    </>
  );
}
