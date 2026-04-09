// Policy rollout coverage: for each policy, what fraction of
// applicable devices have been evaluated? Fleet shows a pending count
// but not a visual progress bar leadership can scan. This makes
// deployment completeness visible at a glance.

import type { PolicyRanking, Severity } from "../types";

interface Props {
  policies: PolicyRanking[];
}

const SEVERITY_DOTS: Record<Severity, string> = {
  critical: "bg-severity-critical",
  high: "bg-severity-high",
  medium: "bg-severity-medium",
  low: "bg-severity-low",
};

export default function PolicyCoverage({ policies }: Props) {
  return (
    <div className="card px-6 py-5">
      <h2 className="text-[14px] font-semibold text-neutral-700 mb-4">
        Policy Rollout Coverage
      </h2>
      <div className="space-y-2.5">
        {policies.map((p) => {
          const evaluated = p.pass_count + p.fail_count;
          const pct = p.applicable_count
            ? Math.round((evaluated / p.applicable_count) * 100)
            : 0;
          return (
            <div key={p.policy_id} className="flex items-center gap-3">
              <span
                className={`inline-block w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOTS[p.severity]}`}
              />
              <span className="text-[12px] text-neutral-700 w-[220px] truncate shrink-0">
                {p.name}
              </span>
              <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-[11px] text-neutral-500 w-20 text-right shrink-0">
                {evaluated} / {p.applicable_count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
