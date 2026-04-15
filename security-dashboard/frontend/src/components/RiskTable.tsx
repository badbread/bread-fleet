// Risk concentration table: the 10 devices with the highest weighted
// failure scores. This "problem children" list doesn't exist in Fleet.
// Fleet can sort hosts by policy count, but not by severity-weighted
// risk. A device failing two critical policies (score 8) ranks higher
// than one failing four low policies (score 4).

import type { DeviceRisk } from "../types";

interface Props {
  devices: DeviceRisk[];
}

const PLATFORM_LABELS: Record<string, string> = {
  darwin: "macOS",
  ubuntu: "Linux",
  windows: "Windows",
};

function riskBadge(score: number): string {
  if (score >= 8) return "severity-badge-critical";
  if (score >= 5) return "severity-badge-high";
  if (score >= 3) return "severity-badge-medium";
  return "severity-badge-low";
}

export default function RiskTable({ devices }: Props) {
  return (
    <div className="card px-6 py-5">
      <h2 className="text-[14px] font-semibold text-white mb-4">
        Highest Risk Devices
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-[#9B9A97] border-b border-[#3A3936]">
              <th className="pb-2 pr-4 font-medium">Hostname</th>
              <th className="pb-2 pr-4 font-medium">Platform</th>
              <th className="pb-2 pr-4 font-medium text-right">Failures</th>
              <th className="pb-2 font-medium text-right">Risk</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr
                key={d.hostname}
                className="border-b border-[#3A3936] last:border-b-0"
              >
                <td className="py-2 pr-4 font-medium text-[#E9E9E7]">
                  {d.hostname}
                </td>
                <td className="py-2 pr-4 text-[#9B9A97]">
                  {PLATFORM_LABELS[d.platform] ?? d.platform}
                </td>
                <td className="py-2 pr-4 text-right text-[#9B9A97]">
                  {d.fail_count} / {d.total_policies}
                </td>
                <td className="py-2 text-right">
                  <span className={`severity-badge ${riskBadge(d.risk_score)}`}>
                    {d.risk_score}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {devices.length > 0 && (
        <p className="mt-3 text-[11px] text-[#9B9A97]">
          Risk score = sum of severity weights for all failing policies on the device
        </p>
      )}
    </div>
  );
}
