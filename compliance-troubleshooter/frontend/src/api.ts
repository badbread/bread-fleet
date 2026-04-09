// Backend API client. Thin fetch wrappers, one function per endpoint.
// Errors are surfaced as thrown Error instances with the backend's
// detail message attached so the components can render them in their
// error states.

import type {
  HostCompliance,
  HostSearchResult,
  RemediationResponse,
} from "./types";

// Backend URL. Baked at build time via Vite's env var injection. The
// dev server uses the value from .env in the frontend directory; the
// production build uses the VITE_BACKEND_URL build arg from
// docker-compose.yml.
const BACKEND = (import.meta.env.VITE_BACKEND_URL as string) ?? "http://localhost:8088";

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
  const url = new URL(`${BACKEND}/api/hosts/search`);
  url.searchParams.set("q", query);
  const r = await fetch(url.toString());
  const body = await jsonOr(r);
  return body.hosts ?? [];
}

export async function getHostCompliance(hostname: string): Promise<HostCompliance> {
  const r = await fetch(`${BACKEND}/api/hosts/${encodeURIComponent(hostname)}/compliance`);
  return jsonOr(r);
}

export async function runRemediation(
  hostname: string,
  remediationId: string,
): Promise<RemediationResponse> {
  const r = await fetch(
    `${BACKEND}/api/hosts/${encodeURIComponent(hostname)}/remediate/${encodeURIComponent(remediationId)}`,
    { method: "POST" },
  );
  return jsonOr(r);
}
