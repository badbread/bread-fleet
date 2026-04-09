// Backend API client. Thin fetch wrappers, one function per endpoint.
// Errors are surfaced as thrown Error instances with the backend's
// detail message attached so the components can render them in their
// error states.
//
// Same-origin design: the portal gateway proxies /compliance/api/ to
// the backend. API paths are anchored to Vite's BASE_URL so the same
// code works both behind the portal (/compliance/api/...) and in
// standalone dev (/api/...).

import type {
  HostCompliance,
  HostSearchResult,
  RemediationResponse,
} from "./types";

const BASE = import.meta.env.BASE_URL;

async function jsonOr(throwOn: Response): Promise<any> {
  if (!throwOn.ok) {
    let detail: string;
    try {
      const body = await throwOn.json();
      detail = body.detail ?? throwOn.statusText;
    } catch {
      detail = throwOn.statusText;
    }
    throw new Error(`Backend ${throwOn.status}: ${detail}`);
  }
  return throwOn.json();
}

export async function searchHosts(query: string): Promise<HostSearchResult[]> {
  const url = new URL(`${BASE}api/hosts/search`, window.location.origin);
  url.searchParams.set("q", query);
  const r = await fetch(url.toString());
  const body = await jsonOr(r);
  return body.hosts ?? [];
}

export async function getHostCompliance(hostname: string): Promise<HostCompliance> {
  const r = await fetch(`${BASE}api/hosts/${encodeURIComponent(hostname)}/compliance`);
  return jsonOr(r);
}

export async function runRemediation(
  hostname: string,
  remediationId: string,
): Promise<RemediationResponse> {
  const r = await fetch(
    `${BASE}api/hosts/${encodeURIComponent(hostname)}/remediate/${encodeURIComponent(remediationId)}`,
    { method: "POST" },
  );
  return jsonOr(r);
}
