// Center panel: selected KEV entry detail with generated osquery SQL,
// mapping status badge, and deploy/dry-run controls.

import { useState } from "react";
import type { MappedKev, DeployedPolicy } from "../types";
import { deployKev } from "../api";
import MappingBadge from "./MappingBadge";
import SqlPreview from "./SqlPreview";

interface Props {
  mapped: MappedKev;
  onDeployed: (policy: DeployedPolicy) => void;
}

export default function KevDetail({ mapped, onDeployed }: Props) {
  const [deploying, setDeploying] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<DeployedPolicy | null>(null);

  const { kev, status, osquery_sql, mapping_reason, confidence } = mapped;

  const handleDeploy = async () => {
    setDeploying(true);
    setError(null);
    try {
      const result = await deployKev(kev.cve_id, dryRun);
      setLastResult(result);
      onDeployed(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className="px-5 py-4 space-y-4 overflow-y-auto h-full">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-[16px] font-semibold text-neutral-700">
            {kev.cve_id}
          </h2>
          <MappingBadge status={status} />
          {kev.known_ransomware_campaign_use === "Known" && (
            <span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase bg-severity-critical-bg text-severity-critical rounded">
              Ransomware
            </span>
          )}
        </div>
        <p className="text-[13px] text-neutral-700 leading-relaxed">
          {kev.short_description}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-[12px]">
        <div>
          <span className="text-neutral-500">Vendor</span>
          <p className="text-neutral-700 font-medium">{kev.vendor_project}</p>
        </div>
        <div>
          <span className="text-neutral-500">Product</span>
          <p className="text-neutral-700 font-medium">{kev.product}</p>
        </div>
        <div>
          <span className="text-neutral-500">Added to KEV</span>
          <p className="text-neutral-700 font-medium">{kev.date_added}</p>
        </div>
        <div>
          <span className="text-neutral-500">Due date</span>
          <p className="text-neutral-700 font-medium">{kev.due_date}</p>
        </div>
      </div>

      <div>
        <p className="text-[12px] text-neutral-500 mb-1">Required action</p>
        <p className="text-[13px] text-neutral-700 leading-relaxed">
          {kev.required_action}
        </p>
      </div>

      <div>
        <p className="text-[12px] text-neutral-500 mb-1">Mapping</p>
        <p className="text-[13px] text-neutral-700">{mapping_reason}</p>
        {confidence && (
          <p className="text-[12px] text-neutral-500 mt-0.5">
            Confidence: <span className="font-medium">{confidence}</span>
          </p>
        )}
      </div>

      {osquery_sql && (
        <div>
          <p className="text-[12px] text-neutral-500 mb-2">
            Generated osquery SQL
          </p>
          <SqlPreview sql={osquery_sql} />

          {status === "claude_assisted" && (
            <p className="mt-2 text-[12px] text-mapping-claude font-medium">
              AI-generated query — review before deploying
            </p>
          )}

          <div className="mt-3 flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-[12px] text-neutral-500 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="rounded"
              />
              Dry run (preview only)
            </label>
            <button
              onClick={handleDeploy}
              disabled={deploying}
              className={`px-4 py-1.5 text-[13px] font-medium rounded-md transition-colors ${
                dryRun
                  ? "bg-neutral-100 text-neutral-700 hover:bg-neutral-200"
                  : "bg-accent text-white hover:bg-accent/90"
              } disabled:opacity-50`}
            >
              {deploying ? "Deploying..." : dryRun ? "Preview" : "Deploy to Fleet"}
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-[13px] text-severity-critical">{error}</p>
      )}

      {lastResult && (
        <div className="card px-4 py-3">
          <p className="text-[12px] text-neutral-500">
            {lastResult.dry_run ? "Dry run result" : "Deployed"}
          </p>
          <p className="text-[13px] text-neutral-700 font-medium mt-1">
            {lastResult.policy_name}
          </p>
          {lastResult.fleet_policy_id && (
            <p className="text-[12px] text-neutral-500 mt-0.5">
              Fleet policy ID: {lastResult.fleet_policy_id}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
