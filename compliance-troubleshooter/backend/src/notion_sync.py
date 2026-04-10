"""Fire-and-forget Notion sync for compliance events.

When NOTION_API_TOKEN and NOTION_DATABASE_ID are set, every compliance
check and remediation action creates a row in the Notion database. The
sync is non-blocking (asyncio.create_task) so it never slows down the
API response to the frontend.

If the Notion API is down or rate-limited, the failure is logged and
swallowed. The troubleshooter continues working without it, and the
JSONL audit log remains the authoritative record. Notion is a
convenience view, not the source of truth.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

PLATFORM_MAP = {
    "ubuntu": "Linux",
    "darwin": "macOS",
    "windows": "Windows",
    "ios": "iOS",
    "linux": "Linux",
}


class NotionSync:
    """Pushes compliance events to a Notion database."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = bool(settings.notion_api_token and settings.notion_database_id)
        self._database_id = settings.notion_database_id or ""
        self._portal_url = settings.notion_portal_url

        if self._enabled:
            self._client = httpx.AsyncClient(
                base_url=NOTION_API_BASE,
                headers={
                    "Authorization": f"Bearer {settings.notion_api_token}",
                    "Notion-Version": NOTION_VERSION,
                    "Content-Type": "application/json",
                    "User-Agent": "fleet-compliance-sync/0.1.0",
                },
                timeout=15.0,
            )
            logger.info("notion sync enabled (database=%s)", self._database_id)
        else:
            self._client = None
            logger.info("notion sync disabled (no NOTION_API_TOKEN or NOTION_DATABASE_ID)")

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def push_compliance_event(
        self,
        hostname: str,
        platform: str,
        policy_name: str,
        severity: str,
        root_cause: str,
        remediation: str,
        status: str,
        resolved_by: str = "",
    ) -> None:
        """Push a single compliance event to Notion. Fire-and-forget safe."""
        if not self._enabled or not self._client:
            return

        try:
            await self._create_page(
                hostname=hostname,
                platform=PLATFORM_MAP.get(platform, platform),
                policy_name=policy_name,
                severity=severity.capitalize(),
                root_cause=root_cause,
                remediation=remediation,
                status=status,
                resolved_by=resolved_by,
            )
            logger.info("notion: pushed event for %s / %s", hostname, policy_name)
        except Exception as exc:
            # Swallow all errors. Notion is a convenience, not critical path.
            logger.warning("notion sync failed: %s", exc)

    async def _create_page(
        self,
        hostname: str,
        platform: str,
        policy_name: str,
        severity: str,
        root_cause: str,
        remediation: str,
        status: str,
        resolved_by: str,
    ) -> None:
        assert self._client is not None

        properties = {
            "Device": {"title": [{"text": {"content": hostname}}]},
            "Platform": {"select": {"name": platform}},
            "Failed Policy": {"rich_text": [{"text": {"content": policy_name[:2000]}}]},
            "Severity": {"select": {"name": severity}},
            "Root Cause": {"rich_text": [{"text": {"content": root_cause[:2000]}}]},
            "Remediation": {"rich_text": [{"text": {"content": remediation[:2000]}}]},
            "Status": {"select": {"name": status}},
            "Resolved By": {"rich_text": [{"text": {"content": resolved_by}}]},
            "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            "Source": {"url": f"{self._portal_url}/compliance/"},
        }

        resp = await self._client.post("/pages", json={
            "parent": {"database_id": self._database_id},
            "properties": properties,
        })
        if resp.status_code == 429:
            # Rate limited. Log and move on.
            logger.warning("notion rate limited, skipping this event")
            return
        resp.raise_for_status()


def fire_and_forget_notion(
    notion: NotionSync,
    hostname: str,
    platform: str,
    policy_name: str,
    severity: str,
    root_cause: str,
    remediation: str,
    status: str,
    resolved_by: str = "",
) -> None:
    """Schedule a Notion push without awaiting it.

    Called from the compliance fetch and remediation routes. The task
    runs in the background and any errors are swallowed by the
    NotionSync.push_compliance_event method.
    """
    if not notion.enabled:
        return

    asyncio.create_task(
        notion.push_compliance_event(
            hostname=hostname,
            platform=platform,
            policy_name=policy_name,
            severity=severity,
            root_cause=root_cause,
            remediation=remediation,
            status=status,
            resolved_by=resolved_by,
        )
    )
