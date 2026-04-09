"""Claude-assisted osquery SQL generation for unknown KEV products.

When the curated registry has no entry for a KEV vulnerability, this
module asks Claude to generate an osquery detection query. The prompt
includes the available osquery tables, the entry's vendor/product/
description, and example SQL patterns from the registry.

Claude-generated SQL is never auto-deployed. The UI shows it with a
"Claude-assisted" badge and a confidence indicator, requiring manual
approval before deployment to Fleet.
"""

import json
import logging
from typing import Optional

from .models import KevEntry, MappedKev, MappingStatus

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an osquery SQL expert helping a Fleet device management team \
detect known exploited vulnerabilities on enrolled Linux hosts.

Given a CISA KEV vulnerability entry, generate an osquery SQL query \
that detects whether the vulnerable software is installed on a host.

Available osquery tables for detection:
- deb_packages (name, version, source, arch) — Debian/Ubuntu packages
- rpm_packages (name, version, release, arch) — RHEL/CentOS packages
- os_version (name, version, major, minor, patch, platform) — OS info
- chrome_extensions (name, version, browser_type) — browser extensions
- firefox_addons (name, version) — Firefox extensions
- python_packages (name, version) — pip packages
- npm_packages (name, version) — Node.js packages

Fleet policy convention: the query must return 1 row when the host \
PASSES (is NOT vulnerable) and 0 rows when it FAILS (IS vulnerable).

Pattern for "host is vulnerable if package X is installed":
  SELECT 1 WHERE NOT EXISTS (
    SELECT 1 FROM deb_packages WHERE name = 'package_name'
  );

Pattern for "host is vulnerable if package X version is below Y":
  SELECT 1 FROM deb_packages
  WHERE name = 'package_name'
  AND version >= 'safe_version';

Respond with valid JSON only:
{
  "osquery_sql": "the SQL query",
  "osquery_table": "primary table used",
  "mapping_reason": "1-sentence explanation of the detection strategy",
  "confidence": "high" | "medium" | "low",
  "platform": "linux"
}

If the product cannot be detected via osquery, respond:
{"unmappable": true, "reason": "why it can't be detected"}
"""


async def generate_mapping(
    entry: KevEntry,
    *,
    api_key: str,
    model: str = "claude-sonnet-4-5",
) -> Optional[MappedKev]:
    """Ask Claude to generate an osquery detection query for a KEV entry."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, skipping Claude mapper")
        return None

    user_prompt = (
        f"CISA KEV entry:\n"
        f"  CVE ID: {entry.cve_id}\n"
        f"  Vendor: {entry.vendor_project}\n"
        f"  Product: {entry.product}\n"
        f"  Vulnerability: {entry.vulnerability_name}\n"
        f"  Description: {entry.short_description}\n"
        f"  Required Action: {entry.required_action}\n"
        f"\n"
        f"Generate an osquery detection query for this vulnerability "
        f"targeting Linux (Ubuntu/Debian) hosts."
    )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        message = await client.messages.create(
            model=model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        logger.warning("Claude API call failed: %s", exc)
        return None

    # Parse Claude's response.
    text = message.content[0].text.strip()

    # Strip markdown code fences if present.
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Claude returned non-JSON response: %s", text[:200])
        return None

    if data.get("unmappable"):
        return None

    return MappedKev(
        kev=entry,
        status=MappingStatus.CLAUDE_ASSISTED,
        osquery_sql=data.get("osquery_sql"),
        osquery_table=data.get("osquery_table"),
        mapping_reason=data.get("mapping_reason", "Claude-generated mapping"),
        confidence=data.get("confidence", "low"),
        platform=data.get("platform", "linux"),
    )
