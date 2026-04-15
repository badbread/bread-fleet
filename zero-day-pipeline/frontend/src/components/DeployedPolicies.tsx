// Right panel: deployed policies list with per-host pass/fail results.
// Polls for host results after a new deployment.

import { useState, useEffect, useCallback } from "react";
import type { DeployedPolicy, HostResult } from "../types";
import { getDeployedPolicies, getPolicyResults, deletePolicy } from "../api";

interface Props {
  refreshTrigger: number;
}

export default function DeployedPolicies({ refreshTrigger }: Props) {
  const [policies, setPolicies] = useState<DeployedPolicy[]>([]);
  const [results, setResults] = useState<Record<number, HostResult[]>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const deployed = await getDeployedPolicies();
      setPolicies(deployed);

      // Fetch results for each real (non-dry-run) policy.
      const newResults: Record<number, HostResult[]> = {};
      for (const p of deployed) {
        if (p.fleet_policy_id && !p.dry_run) {
          try {
            newResults[p.fleet_policy_id] = await getPolicyResults(p.fleet_policy_id);
          } catch {
            // Results may not be available yet.
          }
        }
      }
      setResults(newResults);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshTrigger]);

  // Poll for results after a new deployment.
  useEffect(() => {
    if (refreshTrigger === 0) return;
    const interval = setInterval(load, 5000);
    const timeout = setTimeout(() => clearInterval(interval), 30000);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [refreshTrigger, load]);

  const handleDelete = async (policyId: number) => {
    try {
      await deletePolicy(policyId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-[#3A3936]">
        <h2 className="text-[14px] font-semibold text-white">
          Deployed Policies
        </h2>
        <p className="text-[11px] text-[#9B9A97] mt-0.5">
          {policies.length} {policies.length === 1 ? "policy" : "policies"}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {error && (
          <p className="px-4 py-4 text-[13px] text-severity-critical">{error}</p>
        )}

        {policies.length === 0 && !error && (
          <p className="px-4 py-6 text-[13px] text-[#9B9A97] text-center">
            No policies deployed yet. Select a KEV entry and deploy it.
          </p>
        )}

        {policies.map((p) => {
          const hostResults = p.fleet_policy_id ? results[p.fleet_policy_id] || [] : [];
          return (
            <div
              key={`${p.cve_id}-${p.deployed_at}`}
              className="px-4 py-3 border-b border-[#3A3936]"
            >
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-[#E9E9E7]">
                  {p.cve_id}
                </span>
                {p.dry_run ? (
                  <span className="text-[10px] font-semibold uppercase text-[#9B9A97] bg-[#3A3936] px-1.5 py-0.5 rounded">
                    Dry run
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold uppercase text-mapping-mapped bg-mapping-mapped-bg px-1.5 py-0.5 rounded">
                    Live
                  </span>
                )}
              </div>
              <p className="text-[12px] text-[#9B9A97] mt-0.5 truncate">
                {p.policy_name}
              </p>

              {hostResults.length > 0 && (
                <div className="mt-2 space-y-1">
                  {hostResults.map((hr) => (
                    <div
                      key={hr.hostname}
                      className="flex items-center gap-2 text-[12px]"
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          hr.status === "pass"
                            ? "bg-mapping-mapped"
                            : hr.status === "fail"
                              ? "bg-severity-critical"
                              : "bg-neutral-300"
                        }`}
                      />
                      <span className="text-[#E9E9E7]">{hr.hostname}</span>
                      <span className="text-[#9B9A97]">{hr.status}</span>
                    </div>
                  ))}
                </div>
              )}

              {p.fleet_policy_id && !p.dry_run && (
                <button
                  onClick={() => handleDelete(p.fleet_policy_id!)}
                  className="mt-2 text-[11px] text-severity-critical hover:underline"
                >
                  Remove from Fleet
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
