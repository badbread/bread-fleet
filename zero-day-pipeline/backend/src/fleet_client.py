"""Fleet REST API client for policy management.

Follows the same pattern as the Compliance Troubleshooter's client:
async httpx, single exception type, connection pooling, verify=False
for the self-signed LAN cert.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class FleetClientError(Exception):
    """Any failure talking to the Fleet REST API."""


class FleetClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            verify=False,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ----------------------------------------------------------------
    # Policy CRUD
    # ----------------------------------------------------------------

    async def create_policy(
        self,
        *,
        name: str,
        query: str,
        description: str = "",
        resolution: str = "",
        platform: str = "linux",
        critical: bool = False,
    ) -> dict[str, Any]:
        """Create a new global policy in Fleet.

        Returns the full policy dict including the assigned ID.
        """
        payload = {
            "name": name,
            "query": query,
            "description": description,
            "resolution": resolution,
            "platform": platform,
            "critical": critical,
        }
        return await self._post("/api/latest/fleet/global/policies", payload)

    async def delete_policy(self, policy_id: int) -> None:
        """Delete a global policy by ID."""
        await self._post(
            "/api/latest/fleet/global/policies/delete",
            {"ids": [policy_id]},
        )

    async def list_policies(self) -> list[dict[str, Any]]:
        """List all global policies."""
        data = await self._get("/api/latest/fleet/global/policies")
        return data.get("policies") or []

    async def get_policy(self, policy_id: int) -> dict[str, Any]:
        """Get a single policy with host pass/fail counts."""
        return await self._get(f"/api/latest/fleet/global/policies/{policy_id}")

    # ----------------------------------------------------------------
    # Hosts
    # ----------------------------------------------------------------

    async def list_hosts(
        self, *, policy_id: Optional[int] = None, policy_status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List hosts, optionally filtered by policy pass/fail status."""
        params: dict[str, Any] = {}
        if policy_id is not None:
            params["policy_id"] = policy_id
        if policy_status:
            params["policy_status"] = policy_status
        data = await self._get("/api/latest/fleet/hosts", params=params)
        return data.get("hosts") or []

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    async def _get(
        self, path: str, *, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            detail = _extract_fleet_error(exc.response)
            raise FleetClientError(
                f"Fleet API {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise FleetClientError(f"Fleet API error: {exc}") from exc

    async def _post(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()
        except httpx.HTTPStatusError as exc:
            detail = _extract_fleet_error(exc.response)
            raise FleetClientError(
                f"Fleet API {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise FleetClientError(f"Fleet API error: {exc}") from exc


def _extract_fleet_error(response: httpx.Response) -> str:
    """Pull the human-readable error from Fleet's JSON response."""
    try:
        data = response.json()
        errors = data.get("errors", [])
        if errors:
            return errors[0].get("reason", str(data))
        return data.get("message", str(data))
    except Exception:
        return response.text[:200]
