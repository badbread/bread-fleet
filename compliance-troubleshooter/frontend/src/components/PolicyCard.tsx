// PolicyCard renders one translated failing policy: summary, impact,
// fix steps, and a Fix button that triggers a simulated console
// showing the remediation script running. The simulation is honest
// about being simulated and explains why (Fleet Free API limitation).

import { useState } from "react";
import type { TranslatedPolicy } from "../types";
import SimulatedConsole from "./SimulatedConsole";

interface Props {
  hostname: string;
  policy: TranslatedPolicy;
  onRemediated: () => void;
}

export default function PolicyCard({ hostname, policy, onRemediated }: Props) {
  const [showConsole, setShowConsole] = useState(false);

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

        {/* Fix button: shows for policies with an automated remediation path */}
        {policy.support_can_fix_themselves && policy.automated_remediation_id && !showConsole && (
          <div className="mt-5 pt-4 border-t border-neutral-100">
            <button
              type="button"
              onClick={() => setShowConsole(true)}
              className="btn-primary"
            >
              Fix it now
            </button>
          </div>
        )}

        {/* Simulated console showing the fix running */}
        {showConsole && policy.automated_remediation_id && (
          <SimulatedConsole
            remediationId={policy.automated_remediation_id}
            hostname={hostname}
            onComplete={onRemediated}
          />
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
