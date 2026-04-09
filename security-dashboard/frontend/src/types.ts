// Response shapes from the dashboard backend. Mirrors the Pydantic
// models in backend/src/models.py.

export type Severity = "low" | "medium" | "high" | "critical";

export interface PlatformSummary {
  platform: string;
  device_count: number;
  fully_compliant: number;
  health_score: number;
}

export interface PostureSummary {
  health_score: number;
  device_count: number;
  total_checks: number;
  platforms: PlatformSummary[];
}

export interface TrendPoint {
  date: string;
  health_score: number;
  device_count: number;
  events: string[];
}

export interface PolicyRanking {
  policy_id: number;
  name: string;
  severity: Severity;
  weight: number;
  fail_count: number;
  pass_count: number;
  applicable_count: number;
  fail_rate: number;
}

export interface DeviceRisk {
  hostname: string;
  platform: string;
  os_version: string;
  last_seen: string;
  fail_count: number;
  total_policies: number;
  risk_score: number;
}
