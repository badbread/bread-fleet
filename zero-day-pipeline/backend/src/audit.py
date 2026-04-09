"""JSONL audit logger for the Zero-Day Response Pipeline.

Same pattern as the Compliance Troubleshooter: append-only, never
raises, and never breaks user flow. Every KEV fetch, mapping,
deployment, and deletion is recorded.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    KEV_FEED_POLL = "kev_feed_poll"
    POLICY_MAPPED = "policy_mapped"
    POLICY_DEPLOYED = "policy_deployed"
    POLICY_DELETED = "policy_deleted"


class AuditLogger:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        action: AuditAction,
        *,
        cve_id: Optional[str] = None,
        detail: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action.value,
        }
        if cve_id:
            entry["cve_id"] = cve_id
        if detail:
            entry["detail"] = detail
        if extra:
            entry.update(extra)

        try:
            with open(self._path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("audit write failed: %s", exc)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            lines = self._path.read_text().strip().splitlines()
            entries = [json.loads(line) for line in lines[-limit:]]
            entries.reverse()
            return entries
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("audit read failed: %s", exc)
            return []
