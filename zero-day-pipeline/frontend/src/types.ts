// Response shapes from the zero-day pipeline backend.

export interface KevEntry {
  cveID: string;
  vendorProject: string;
  product: string;
  vulnerabilityName: string;
  dateAdded: string;
  shortDescription: string;
  requiredAction: string;
  dueDate: string;
  knownRansomwareCampaignUse: string;
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
