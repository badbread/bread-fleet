// Dashboard API client. Same-origin design: the portal nginx proxies
// /dashboard/api/ to the backend, so every call uses a relative URL
// anchored to Vite's BASE_URL. Works identically in standalone dev
// and behind the portal.

import type {
  PostureSummary,
  TrendPoint,
  PolicyRanking,
  DeviceRisk,
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

export async function getSummary(): Promise<PostureSummary> {
  const r = await fetch(`${BASE}api/posture/summary`);
  return jsonOr(r);
}

export async function getTrend(days = 30): Promise<TrendPoint[]> {
  const r = await fetch(`${BASE}api/posture/trend?days=${days}`);
  return jsonOr(r);
}

export async function getPolicies(): Promise<PolicyRanking[]> {
  const r = await fetch(`${BASE}api/posture/policies`);
  return jsonOr(r);
}

export async function getDevices(): Promise<DeviceRisk[]> {
  const r = await fetch(`${BASE}api/posture/devices`);
  return jsonOr(r);
}
