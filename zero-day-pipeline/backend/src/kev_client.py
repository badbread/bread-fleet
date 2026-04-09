"""Async CISA KEV feed client with in-memory caching.

Fetches the full KEV JSON catalog and caches it for a configurable
TTL. The feed is ~1200 entries and fits comfortably in memory. The
cache avoids hammering CISA's server during a demo session where
the interviewer is clicking through entries.
"""

import logging
import time
from typing import Optional

import httpx

from .models import KevEntry

logger = logging.getLogger(__name__)


class KevClient:
    def __init__(self, feed_url: str, cache_ttl: int = 3600):
        self._feed_url = feed_url
        self._cache_ttl = cache_ttl
        self._cache: Optional[list[KevEntry]] = None
        self._cache_time: float = 0
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_feed(self, *, force: bool = False) -> list[KevEntry]:
        """Return the full KEV catalog, using cache if fresh."""
        now = time.monotonic()
        if not force and self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        logger.info("fetching KEV feed from %s", self._feed_url)
        resp = await self._client.get(self._feed_url)
        resp.raise_for_status()
        data = resp.json()

        entries = [KevEntry.model_validate(v) for v in data.get("vulnerabilities", [])]
        # Most recent first.
        entries.sort(key=lambda e: e.date_added, reverse=True)

        self._cache = entries
        self._cache_time = now
        logger.info("cached %d KEV entries", len(entries))
        return entries

    async def get_entry(self, cve_id: str) -> Optional[KevEntry]:
        """Look up a single CVE by ID."""
        entries = await self.fetch_feed()
        cve_upper = cve_id.upper()
        for entry in entries:
            if entry.cve_id == cve_upper:
                return entry
        return None

    async def filter_feed(
        self,
        *,
        days: Optional[int] = None,
        product: Optional[str] = None,
        ransomware_only: bool = False,
    ) -> list[KevEntry]:
        """Filter the cached feed by date recency, product name, or
        ransomware campaign flag."""
        from datetime import date, timedelta

        entries = await self.fetch_feed()

        if days is not None:
            cutoff = str(date.today() - timedelta(days=days))
            entries = [e for e in entries if e.date_added >= cutoff]

        if product:
            product_lower = product.lower()
            entries = [
                e for e in entries
                if product_lower in e.product.lower()
                or product_lower in e.vendor_project.lower()
            ]

        if ransomware_only:
            entries = [
                e for e in entries
                if e.known_ransomware_campaign_use == "Known"
            ]

        return entries
