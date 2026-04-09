// Platform compliance comparison. Shows macOS, Linux, and Windows
// health scores side by side so leadership can see at a glance which
// fleet segment needs attention. Fleet lets you filter by platform
// but doesn't present a direct comparison.

import type { PlatformSummary } from "../types";

interface Props {
  platforms: PlatformSummary[];
}

const PLATFORM_LABELS: Record<string, string> = {
  darwin: "macOS",
  ubuntu: "Linux",
  windows: "Windows",
};

const PLATFORM_COLORS: Record<string, string> = {
  darwin: "bg-neutral-700",
  ubuntu: "bg-severity-high",
  windows: "bg-accent",
};

function scoreColor(score: number): string {
  if (score >= 90) return "text-green-600";
  if (score >= 75) return "text-severity-medium";
  return "text-severity-critical";
}

export default function PlatformBreakdown({ platforms }: Props) {
  return (
    <div className="card px-6 py-5 h-full">
      <h2 className="text-[14px] font-semibold text-neutral-700 mb-4">
        Platform Compliance
      </h2>
      <div className="space-y-4">
        {platforms.map((p) => (
          <div key={p.platform}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[13px] font-medium text-neutral-700">
                {PLATFORM_LABELS[p.platform] ?? p.platform}
              </span>
              <span className="text-[12px] text-neutral-500">
                {p.device_count} devices
                {" / "}
                {p.fully_compliant} fully compliant
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-3 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${PLATFORM_COLORS[p.platform] ?? "bg-accent"}`}
                  style={{ width: `${p.health_score}%` }}
                />
              </div>
              <span className={`text-[14px] font-semibold w-14 text-right ${scoreColor(p.health_score)}`}>
                {p.health_score}%
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-[11px] text-neutral-300">
        Health scores are severity-weighted, not raw pass/fail ratios
      </p>
    </div>
  );
}
