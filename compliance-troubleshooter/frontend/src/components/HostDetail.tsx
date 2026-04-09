// Host detail panel. Renders the compliance summary at the top
// (pass/fail/pending counts) and the failing policies as a stack of
// PolicyCard components below. Includes the Re-check button that
// triggers a re-fetch in the parent.

import type { HostCompliance } from "../types";
import PolicyCard from "./PolicyCard";

interface Props {
  host: HostCompliance;
  onRecheck: () => void;
}

export default function HostDetail({ host, onRecheck }: Props) {
  const allGood = host.fail_count === 0 && host.pending_count === 0;

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="p-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[18px] font-semibold text-neutral-700">
              {host.hostname}
            </h2>
            <p className="mt-1 text-[13px] text-neutral-500">
              {host.platform} &middot; {host.os_version} &middot; {host.status}
            </p>
            <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
              <span>
                <span className="font-semibold text-[#0F7B6C]">{host.pass_count}</span>{" "}
                <span className="text-neutral-500">passing</span>
              </span>
              <span>
                <span className="font-semibold text-severity-critical">{host.fail_count}</span>{" "}
                <span className="text-neutral-500">failing</span>
              </span>
              {host.pending_count > 0 && (
                <span>
                  <span className="font-semibold text-neutral-500">{host.pending_count}</span>{" "}
                  <span className="text-neutral-500">pending</span>
                </span>
              )}
            </p>
          </div>
          <button type="button" onClick={onRecheck} className="btn-primary shrink-0">
            Re-check
          </button>
        </div>
      </div>

      {allGood && (
        <div
          className="card px-6 py-10 text-center"
          style={{
            backgroundColor: "#F0F7F4",
            borderColor: "#D5E8DE",
            color: "#0F7B6C",
          }}
        >
          <p className="text-[16px] font-semibold">This device is fully compliant.</p>
          <p className="mt-1 text-[13px]">
            No failing policies. Nothing for you to fix here right now.
          </p>
        </div>
      )}

      {host.failing_policies.map((policy) => (
        <PolicyCard
          key={policy.policy_id}
          hostname={host.hostname}
          policy={policy}
          onRemediated={onRecheck}
        />
      ))}
    </div>
  );
}
