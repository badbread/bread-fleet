// Zero-Day Pipeline API client. Same-origin design: the portal nginx
// proxies /zero-day/api/ to the backend.

import type {
  KevFeedResponse,
  MappedKev,
  DeployedPolicy,
  HostResult,
  PipelineStats,
} from "./types";

const BASE = import.meta.env.BASE_URL;

async function jsonOr<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail: string;
    try {
      const body = await resp.json();
      detail = body.detail ?? resp.statusText;
    } catch {
      detail = resp.statusText;
    }
    throw new Error(`Backend ${resp.status}: ${detail}`);
  }
  return resp.json();
}

export async function getKevFeed(params?: {
  days?: number;
  product?: string;
  ransomware_only?: boolean;
}): Promise<KevFeedResponse> {
  const sp = new URLSearchParams();
  if (params?.days) sp.set("days", String(params.days));
  if (params?.product) sp.set("product", params.product);
  if (params?.ransomware_only) sp.set("ransomware_only", "true");
  const q = sp.toString();
  const r = await fetch(`${BASE}api/kev/feed${q ? "?" + q : ""}`);
  return jsonOr(r);
}

export async function mapKev(cveId: string): Promise<MappedKev> {
  const r = await fetch(`${BASE}api/kev/${encodeURIComponent(cveId)}/map`, {
    method: "POST",
  });
  return jsonOr(r);
}

export async function deployKev(
  cveId: string,
  dryRun: boolean,
): Promise<DeployedPolicy> {
  const r = await fetch(`${BASE}api/kev/${encodeURIComponent(cveId)}/deploy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dry_run: dryRun }),
  });
  return jsonOr(r);
}

export async function getDeployedPolicies(): Promise<DeployedPolicy[]> {
  const r = await fetch(`${BASE}api/policies`);
  return jsonOr(r);
}

export async function getPolicyResults(policyId: number): Promise<HostResult[]> {
  const r = await fetch(`${BASE}api/policies/${policyId}/results`);
  return jsonOr(r);
}

export async function deletePolicy(policyId: number): Promise<void> {
  const r = await fetch(`${BASE}api/policies/${policyId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
}

export async function getStats(): Promise<PipelineStats> {
  const r = await fetch(`${BASE}api/stats`);
  return jsonOr(r);
}
