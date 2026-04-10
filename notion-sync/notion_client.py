"""Thin async Notion API client.

Covers only what the compliance sync needs: database creation and page
(row) creation. Uses httpx (already a backend dependency) rather than
adding Notion's official SDK, which pulls in dozens of transitive
dependencies the rest of the stack doesn't need.

Rate limiting: Notion's integration API allows 3 requests per second.
The client handles 429 responses with retry-after backoff. For the seed
script (which creates ~30 pages in sequence) this is fine. For the live
hook in the troubleshooter backend, each compliance check creates one
page, well under the limit.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Async Notion API client for database and page operations."""

    def __init__(self, api_token: str) -> None:
        self._token = api_token
        self._client = httpx.AsyncClient(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "User-Agent": "fleet-compliance-sync/0.1.0",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, json: Optional[dict] = None, retries: int = 3
    ) -> dict:
        """Make an API request with retry-after handling for rate limits."""
        for attempt in range(retries):
            resp = await self._client.request(method, path, json=json)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                logger.warning("notion rate limited, retrying in %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code == 403 and "cloudflare" in resp.text.lower():
                # Cloudflare WAF block. Back off longer and retry.
                wait = 5.0 * (attempt + 1)
                logger.warning("cloudflare block on attempt %d, waiting %.0fs", attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 400:
                logger.error(
                    "notion %s %s -> %d: %s",
                    method, path, resp.status_code, resp.text[:500]
                )
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Notion API failed after {retries} retries on {path}")

    async def create_database(
        self, page_id: str, title: str, properties: dict[str, Any]
    ) -> str:
        """Create a database on a Notion page. Returns the database ID."""
        body = {
            "parent": {"type": "page_id", "page_id": page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        result = await self._request("POST", "/databases", json=body)
        db_id = result["id"]
        logger.info("created notion database %s", db_id)
        return db_id

    async def create_page(self, database_id: str, properties: dict[str, Any]) -> str:
        """Create a page (row) in a Notion database. Returns the page ID."""
        body = {
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": properties,
        }
        result = await self._request("POST", "/pages", json=body)
        return result["id"]


# ------------------------------------------------------------------
# Property builder helpers
# ------------------------------------------------------------------
# Notion's property value format is verbose. These helpers keep the
# seed script and live hook readable.


def prop_title(text: str) -> dict:
    """Title property value (used for the Device column)."""
    return {"title": [{"text": {"content": text}}]}


def prop_rich_text(text: str) -> dict:
    """Rich text property value."""
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def prop_select(name: str) -> dict:
    """Select property value."""
    return {"select": {"name": name}}


def prop_date(iso_date: str) -> dict:
    """Date property value. Accepts ISO 8601 date or datetime string."""
    return {"date": {"start": iso_date}}


def prop_url(url: str) -> dict:
    """URL property value."""
    return {"url": url}


# ------------------------------------------------------------------
# Database schema definition
# ------------------------------------------------------------------

COMPLIANCE_DB_SCHEMA: dict[str, Any] = {
    "Device": {"title": {}},
    "Platform": {
        "select": {
            "options": [
                {"name": "macOS", "color": "gray"},
                {"name": "Linux", "color": "orange"},
                {"name": "Windows", "color": "blue"},
                {"name": "iOS", "color": "green"},
            ]
        }
    },
    "Failed Policy": {"rich_text": {}},
    "Severity": {
        "select": {
            "options": [
                {"name": "Critical", "color": "red"},
                {"name": "High", "color": "orange"},
                {"name": "Medium", "color": "yellow"},
                {"name": "Low", "color": "blue"},
            ]
        }
    },
    "Root Cause": {"rich_text": {}},
    "Remediation": {"rich_text": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Fixed", "color": "green"},
                {"name": "Pending", "color": "yellow"},
                {"name": "Escalated", "color": "red"},
                {"name": "In Progress", "color": "blue"},
            ]
        }
    },
    "Resolved By": {"rich_text": {}},
    "Timestamp": {"date": {}},
    "Source": {"url": {}},
}
