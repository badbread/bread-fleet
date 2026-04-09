"""Fleet REST API client.

Thin async wrapper around Fleet's REST endpoints. Only the endpoints the
troubleshooter actually needs are implemented:

  - GET /api/latest/fleet/hosts/identifier/{name} - host detail with policies
  - GET /api/latest/fleet/hosts?query={hostname}  - host search
  - POST /api/latest/fleet/scripts/run/sync       - run a remediation script

The client never throws raw httpx errors at the calling code: every
network or status failure is normalized into a FleetClientError so the
backend's route handlers have one exception type to catch and translate
into a 5xx response.

Why a custom client and not the official Fleet SDK: there isn't an
official Fleet SDK for Python, and the REST surface is small enough
that maintaining a wrapper is cheaper than depending on a third-party
client that might lag the Fleet release cycle.
"""

import logging
from typing import Any, Optional

import httpx

from .config import Settings
from .models import FleetHost, FleetPolicy

logger = logging.getLogger(__name__)


class FleetClientError(Exception):
    """Raised for any Fleet API failure: network errors, non-2xx
    responses, malformed JSON, missing fields. The route handlers in
    main.py catch this single exception type and convert it to an
    HTTP error response.
    """


class FleetClient:
    """Async client for Fleet's REST API.

    Instantiated once per process via the dependency-injection helper
    in main.py. Reuses a single httpx.AsyncClient under the hood for
    connection pooling and HTTP/2.
    """

    def __init__(self, settings: Settings) -> None:
        # Strip any trailing slash so URL composition is unambiguous.
        # Fleet's API base is conventionally /api/latest/fleet.
        self._base_url = settings.fleet_api_url.rstrip("/")
        self._token = settings.fleet_api_token

        # The Fleet deployment in this repo runs over plain HTTP because
        # of the LAN-only ingress decision in ADR-0003. verify=False is
        # therefore unnecessary; we just talk HTTP. At scale, this would
        # be HTTPS with the Cloudflare-managed cert and verify=True.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )

    async def aclose(self) -> None:
        """Close the underlying httpx client. Called from main.py during
        FastAPI shutdown."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Host endpoints
    # ------------------------------------------------------------------

    async def search_hosts(self, query: str) -> list[dict[str, Any]]:
        """Search for hosts by hostname substring.

        Returns a list of dicts with the minimal fields the frontend
        needs for the search result list (id, hostname, platform,
        status). The full FleetHost model is only returned by
        get_host_detail because it's heavier and the search UI doesn't
        need it.
        """
        url = f"{self._base_url}/api/latest/fleet/hosts"
        try:
            resp = await self._client.get(
                url,
                params={"query": query, "per_page": 25},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("fleet host search failed: %s", exc)
            raise FleetClientError(f"Fleet host search failed: {exc}") from exc

        body = resp.json()
        hosts = body.get("hosts", [])
        return [
            {
                "id": h.get("id"),
                "hostname": h.get("hostname"),
                "platform": h.get("platform", ""),
                "status": h.get("status", "unknown"),
            }
            for h in hosts
        ]

    async def get_host_detail(self, hostname: str) -> FleetHost:
        """Fetch full host detail including policy results.

        Uses Fleet's identifier-based lookup, which accepts hostname,
        UUID, hardware serial, or osquery_host_id. Returns a parsed
        FleetHost or raises FleetClientError if the host doesn't exist
        or Fleet rejects the request.
        """
        # ASSUMPTION: Fleet's hostname identifier is unique within an
        # instance. This holds for the single-tenant deployments the
        # troubleshooter targets. At enterprise scale with team
        # boundaries it remains true because hostnames are
        # globally-unique within Fleet's host model.
        url = f"{self._base_url}/api/latest/fleet/hosts/identifier/{hostname}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FleetClientError(f"Host '{hostname}' not found in Fleet") from exc
            logger.warning("fleet host detail failed: %s", exc)
            raise FleetClientError(f"Fleet host detail failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("fleet host detail network error: %s", exc)
            raise FleetClientError(f"Fleet network error: {exc}") from exc

        host_payload = resp.json().get("host")
        if not host_payload:
            raise FleetClientError(f"Fleet returned no host body for '{hostname}'")

        # Pydantic does the field-by-field validation. We catch its
        # exception and re-raise as our own type so the route handler
        # only has to know about FleetClientError.
        try:
            return FleetHost.model_validate(host_payload)
        except Exception as exc:
            logger.error("malformed Fleet host payload for %s: %s", hostname, exc)
            raise FleetClientError(
                f"Malformed Fleet host payload for '{hostname}'"
            ) from exc

    # ------------------------------------------------------------------
    # Script execution (used by the remediation registry)
    # ------------------------------------------------------------------

    async def run_script_sync(
        self,
        host_id: int,
        script_contents: str,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        """Run a shell script on a host via Fleet's script execution API.

        Synchronous from Fleet's perspective: the API call blocks until
        the script completes (or the per-host timeout fires). Returns
        Fleet's raw execution result for the route handler to translate
        into a RemediationResponse.

        ASSUMPTION: scripts are enabled in the Fleet config (we set
        scripts_disabled: false in gitops/default.yml). At enterprise
        scale this is gated behind a per-team policy and per-script
        approval workflow.
        """
        url = f"{self._base_url}/api/latest/fleet/scripts/run/sync"
        try:
            resp = await self._client.post(
                url,
                json={
                    "host_id": host_id,
                    "script_contents": script_contents,
                    "timeout_secs": timeout_seconds,
                },
                timeout=httpx.Timeout(timeout_seconds + 30.0, connect=5.0),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("fleet script execution failed: %s", exc)
            raise FleetClientError(
                f"Fleet script execution failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("fleet script execution network error: %s", exc)
            raise FleetClientError(f"Fleet network error: {exc}") from exc

        return resp.json()


# ----------------------------------------------------------------------
# Helpers used by the route handlers and the translator
# ----------------------------------------------------------------------


def failing_policies(host: FleetHost) -> list[FleetPolicy]:
    """Return only the policies that have explicitly failed on this host.

    'response' is empty string when osquery has not yet evaluated the
    policy on this host; we treat that as 'unknown' and exclude it from
    the failing list. The frontend shows the count separately so the
    operator knows there are pending evaluations.
    """
    return [p for p in host.policies if p.response == "fail"]


def passing_count(host: FleetHost) -> int:
    return sum(1 for p in host.policies if p.response == "pass")


def pending_count(host: FleetHost) -> int:
    return sum(1 for p in host.policies if not p.response)
