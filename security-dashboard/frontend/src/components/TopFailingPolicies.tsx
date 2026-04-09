// Policies ranked by fleet-wide failure rate. Fleet shows per-policy
// counts but doesn't rank them or weight by severity. This surfaces
// "OS version current fails on 28% of fleet (high severity)" above
// "NTP configured fails on 3% (low severity)" so the team knows
// where to spend remediation effort.

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { PolicyRanking, Severity } from "../types";

interface Props {
  policies: PolicyRanking[];
}

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "#E03E3E",
  high: "#D9730D",
  medium: "#CB912F",
  low: "#0B6E99",
};

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: PolicyRanking }> }) {
  if (!active || !payload?.length) return null;
  const p: PolicyRanking = payload[0].payload;
  return (
    <div className="bg-white border border-neutral-150 rounded-md px-3 py-2 shadow-subtle text-[12px]">
      <p className="font-semibold text-neutral-700">{p.name}</p>
      <p className="text-neutral-500">
        Failing: {p.fail_count} / {p.applicable_count} devices ({p.fail_rate}%)
      </p>
      <p className="text-neutral-500 capitalize">
        Severity: {p.severity} (weight {p.weight}x)
      </p>
    </div>
  );
}

// Truncate long policy names for the Y-axis labels.
function shortName(name: string): string {
  return name.length > 28 ? name.slice(0, 26) + "..." : name;
}

export default function TopFailingPolicies({ policies }: Props) {
  // Show top 8 by failure rate.
  const top = policies.slice(0, 8);

  return (
    <div className="card px-6 py-5">
      <h2 className="text-[14px] font-semibold text-neutral-700 mb-4">
        Top Failing Policies
      </h2>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={top}
            layout="vertical"
            margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#E9E9E7" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 11, fill: "#787774" }}
              tickLine={false}
              axisLine={{ stroke: "#E9E9E7" }}
              tickFormatter={(v: number) => `${v}%`}
              domain={[0, "auto"]}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11, fill: "#787774" }}
              tickLine={false}
              axisLine={false}
              width={180}
              tickFormatter={shortName}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="fail_rate" radius={[0, 3, 3, 0]} barSize={18}>
              {top.map((p) => (
                <Cell
                  key={p.policy_id}
                  fill={SEVERITY_COLORS[p.severity]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex gap-4 text-[11px] text-neutral-500">
        {(["critical", "high", "medium", "low"] as Severity[]).map((s) => (
          <span key={s} className="flex items-center gap-1">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: SEVERITY_COLORS[s] }}
            />
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}
