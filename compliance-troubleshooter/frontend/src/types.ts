// Shape mirrors of the backend's Pydantic models. Kept in sync by hand.
// At enterprise scale a code-gen step would emit these from the
// backend's OpenAPI schema; for the MVP, manual is faster than wiring
// up the codegen.

export type Severity = "low" | "medium" | "high" | "critical";

export interface HostSearchResult {
  id: number;
  hostname: string;
  platform: string;
  status: string;
}

export interface TranslatedPolicy {
  policy_id: number;
  policy_name: string;
  summary: string;
  impact: string;
  fix_steps: string[];
  severity: Severity;
  support_can_fix_themselves: boolean;
  escalate_to: string | null;
  automated_remediation_id: string | null;
}

export interface HostCompliance {
  hostname: string;
  platform: string;
  os_version: string;
  status: string;
  pass_count: number;
  fail_count: number;
  pending_count: number;
  failing_policies: TranslatedPolicy[];
  last_checked: string;
}

export type RemediationOutcome =
  | "succeeded"
  | "failed"
  | "not_implemented"
  | "requires_recheck";

export interface RemediationResponse {
  outcome: RemediationOutcome;
  message: string;
  fleet_script_execution_id: string | null;
}
