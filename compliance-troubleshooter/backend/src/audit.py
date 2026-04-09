"""Audit log writer.

Append-only JSONL file. One line per audited action. Every API call
that does anything (search, fetch compliance, attempt a remediation)
goes through this module before it returns.

The MVP uses a flat file because:
  - Every routing decision in the rest of the code is the same whether
    the storage is JSONL or Postgres
  - JSONL is trivially shippable to any log aggregator that exists
  - The file can be diffed and grep-searched directly during incidents

The at-scale design moves to Postgres with a retention policy and a
SIEM stream, both documented in ADR-0005. The interface stays the same:
record(entry) returns nothing and never raises (audit failures must
not break the user-facing flow).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Settings
from .models import AuditAction, AuditEntry

logger = logging.getLogger(__name__)


class AuditLogger:
    """Append-only JSONL audit logger.

    Thread-unsafe in the sense that two concurrent appends could
    interleave bytes; safe in practice because the file open uses 'a'
    mode which is atomic for writes shorter than PIPE_BUF on Linux
    (4KB), and our entries are well under that. At scale this becomes
    a Postgres insert and the concurrency question becomes the
    database's problem.
    """

    def __init__(self, settings: Settings) -> None:
        self._path: Path = settings.audit_log_path
        # Make sure the parent directory exists. The Compose volume
        # mounts /data which the entrypoint user (uid 10001) owns, so
        # this is a no-op in the standard deployment but matters in
        # tests where audit_log_path can point at a tempdir.
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        action: AuditAction,
        operator: str = "anonymous",
        target_host: Optional[str] = None,
        policy_id: Optional[int] = None,
        outcome: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Append one audit entry. Never raises.

        Audit failures are logged via the standard logger and swallowed
        so a broken disk does not cascade into a 500 on the user-facing
        endpoint. The user can still get help; the audit gap is a
        separate problem the SRE team handles.
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            operator=operator,
            action=action,
            target_host=target_host,
            policy_id=policy_id,
            outcome=outcome,
            detail=detail,
        )

        try:
            line = entry.model_dump_json() + "\n"
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as exc:
            # Log loud but do not raise. The user-facing flow continues.
            logger.error(
                "audit write failed for %s/%s: %s",
                action.value,
                target_host or "-",
                exc,
            )

    def read_recent(
        self,
        host: Optional[str] = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Read the most recent N entries, optionally filtered by host.

        Reads the whole file because JSONL is line-oriented and the
        MVP's expected log size is small (single-operator, single-day
        scenarios). At scale this becomes a SQL query against a Postgres
        index on (target_host, timestamp DESC) with proper pagination.
        """
        if not self._path.exists():
            return []

        results: list[AuditEntry] = []
        try:
            with self._path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            logger.error("audit read failed: %s", exc)
            return []

        # Walk lines newest-first by reversing.
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = AuditEntry.model_validate_json(line)
            except Exception as exc:
                # Malformed line. Skip it; do not let one bad row break
                # the whole read. This shouldn't happen in practice but
                # it's the kind of bug that breaks production at the
                # worst possible moment, so handle it.
                logger.warning("skipping malformed audit line: %s", exc)
                continue
            if host is not None and entry.target_host != host:
                continue
            results.append(entry)
            if len(results) >= limit:
                break

        return results
