// Response shapes from the zero-day pipeline backend.

export interface KevEntry {
  cve_id: string;
  vendor_project: string;
  product: string;
  vulnerability_name: string;
  date_added: string;
  short_description: string;
  required_action: string;
  due_date: string;
  known_ransomware_campaign_use: string;
  notes: string;
}

export type MappingStatus = "mapped" | "claude_assisted" | "unmappable";

export interface MappedKev {
  kev: KevEntry;
  status: MappingStatus;
  osquery_sql: string | null;
  osquery_table: string | null;
  mapping_reason: string;
  confidence: "high" | "medium" | "low" | null;
  platform: string;
}

export interface HostResult {
  hostname: string;
  status: "pass" | "fail" | "pending";
}

export interface DeployedPolicy {
  cve_id: string;
  fleet_policy_id: number | null;
  policy_name: string;
  osquery_sql: string;
  deployed_at: string;
  dry_run: boolean;
  host_results: HostResult[];
}

export interface KevFeedResponse {
  total: number;
  entries: KevEntry[];
}

export interface PipelineStats {
  kev_total: number;
  mapped: number;
  claude_assisted: number;
  unmappable: number;
  deployed: number;
}
