// 30-day compliance trend line chart with event annotations.
// This is the single most important thing the dashboard adds over
// Fleet: historical visibility. Fleet shows NOW. This shows whether
// compliance is improving or degrading, and correlates changes to
// specific events (policy deployments, patch rollouts, new enrollments).

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import type { TrendPoint } from "../types";

interface Props {
  data: TrendPoint[];
}

// Format "2026-03-17" to "Mar 17".
function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TrendPoint }> }) {
  if (!active || !payload?.length) return null;
  const point: TrendPoint = payload[0].payload;
  return (
    <div className="bg-white border border-neutral-150 rounded-md px-3 py-2 shadow-subtle text-[12px]">
      <p className="font-semibold text-neutral-700">{shortDate(point.date)}</p>
      <p className="text-neutral-500">
        Health: <span className="font-medium text-neutral-700">{point.health_score}%</span>
      </p>
      <p className="text-neutral-500">
        Devices: {point.device_count}
      </p>
      {point.events.length > 0 && (
        <div className="mt-1 pt-1 border-t border-neutral-100">
          {point.events.map((e, i) => (
            <p key={i} className="text-accent text-[11px]">{e}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ComplianceTrend({ data }: Props) {
  const eventPoints = data.filter((d) => d.events.length > 0);

  return (
    <div className="card px-6 py-5">
      <h2 className="text-[14px] font-semibold text-neutral-700 mb-4">
        Compliance Trend (30 days)
      </h2>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E9E9E7" />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fontSize: 11, fill: "#787774" }}
              tickLine={false}
              axisLine={{ stroke: "#E9E9E7" }}
              interval={4}
            />
            <YAxis
              domain={[60, 100]}
              tick={{ fontSize: 11, fill: "#787774" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `${v}%`}
              width={44}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="health_score"
              stroke="#2383E2"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#2383E2" }}
            />
            {/* Annotated event markers on the trend line */}
            {eventPoints.map((ep) => (
              <ReferenceDot
                key={ep.date}
                x={ep.date}
                y={ep.health_score}
                r={5}
                fill="#D9730D"
                stroke="#FFFFFF"
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {eventPoints.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
          {eventPoints.map((ep) => (
            <p key={ep.date} className="text-[11px] text-neutral-500">
              <span className="inline-block w-2 h-2 rounded-full bg-severity-high mr-1.5 align-middle" />
              {shortDate(ep.date)}: {ep.events[0]}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
