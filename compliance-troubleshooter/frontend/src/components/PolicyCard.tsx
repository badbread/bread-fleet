// PolicyCard renders one translated failing policy: summary, impact,
// fix steps, and either a Fix button (when the remediation registry
// has an automated handler for this policy) or an "escalate" notice.
//
// The card is the only place in the frontend that calls the
// remediation API. After a remediation completes, it triggers the
// parent's onRemediated callback (which is the same as onRecheck on
// HostDetail) so the whole compliance view re-fetches.

import { useState } from "react";
import type { TranslatedPolicy, RemediationOutcome } from "../types";
import { runRemediation } from "../api";

interface Props {
  hostname: string;
  policy: TranslatedPolicy;
  onRemediated: () => void;
}

export default function PolicyCard({ hostname, policy, onRemediated }: Props) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{
    outcome: RemediationOutcome;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFix = async () => {
    if (!policy.automated_remediation_id) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await runRemediation(hostname, policy.automated_remediation_id);
      setResult({ outcome: r.outcome, message: r.message });
      // If the remediation succeeded or asks for a re-check, refresh
      // the compliance view automatically. The parent will re-render
      // and replace this card with the new policy state.
      if (r.outcome === "succeeded" || r.outcome === "requires_recheck") {
        // Small delay so the operator sees the success message before
        // the card unmounts.
        setTimeout(onRemediated, 1500);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <article className="card">
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-[15px] text-neutral-700 font-medium leading-snug">
              {policy.summary}
            </p>
            <p className="mt-2 text-[13px] text-neutral-500 leading-relaxed">
              <span className="font-medium text-neutral-700">Why it matters: </span>
              {policy.impact}
            </p>
          </div>
          <SeverityBadge severity={policy.severity} />
        </div>

        <div className="mt-4">
          <p className="text-[13px] font-medium text-neutral-700 mb-2">How to fix it:</p>
          <ol className="list-decimal list-inside space-y-1 text-[13px] text-neutral-700 leading-relaxed">
            {policy.fix_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>

        {/* Action area: either a Fix button (automated path) or an
            escalation note (manual path). */}
        {policy.support_can_fix_themselves && policy.automated_remediation_id && (
          <div className="mt-5 pt-4 border-t border-neutral-100">
            <button
              type="button"
              onClick={handleFix}
              disabled={running}
              className="btn-primary"
            >
              {running ? "Running fix..." : "Fix it now"}
            </button>
            {result && (
              <p
                className={
                  "mt-3 text-[13px] " +
                  (result.outcome === "failed" || result.outcome === "not_implemented"
                    ? "text-severity-critical"
                    : "text-[#0F7B6C]")
                }
              >
                {result.message}
              </p>
            )}
            {error && (
              <p className="mt-3 text-[13px] text-severity-critical">Error: {error}</p>
            )}
          </div>
        )}

        {!policy.support_can_fix_themselves && policy.escalate_to && (
          <div className="mt-5 pt-4 border-t border-neutral-100 text-[13px] text-neutral-500">
            This finding needs an engineer. Escalate to:{" "}
            <span className="font-medium text-neutral-700">{policy.escalate_to}</span>
          </div>
        )}

        {policy.support_can_fix_themselves && !policy.automated_remediation_id && (
          <div className="mt-5 pt-4 border-t border-neutral-100 text-[13px] text-neutral-500 italic">
            Manual fix only for now. Walk the user through the steps above.
          </div>
        )}
      </div>
    </article>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls = `severity-badge severity-badge-${severity}`;
  return <span className={cls}>{severity}</span>;
}
