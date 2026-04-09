"""KEV-to-osquery mapping orchestrator.

Tries the curated registry first. If no match, falls back to the
Claude-assisted mapper (when an API key is configured). If neither
can handle the entry, returns an honest "unmappable" result with a
reason string.

This mirrors the Compliance Troubleshooter's translator pattern:
curated first, AI-assisted second, honest about what it can't do.
"""

import logging
from typing import Optional

from .models import KevEntry, MappedKev, MappingStatus
from . import registry as reg

logger = logging.getLogger(__name__)

# Lazy import to avoid requiring anthropic when no key is set.
_claude_mapper = None


def _get_claude_mapper():
    global _claude_mapper
    if _claude_mapper is None:
        from . import claude_mapper
        _claude_mapper = claude_mapper
    return _claude_mapper


async def map_entry(
    entry: KevEntry,
    *,
    anthropic_api_key: str = "",
    anthropic_model: str = "claude-sonnet-4-5",
) -> MappedKev:
    """Map a single KEV entry to an osquery detection query."""

    # Step 1: Try the curated registry.
    reg_entry = reg.lookup(entry.vendor_project, entry.product)
    if reg_entry:
        sql = reg.generate_sql(reg_entry)
        logger.info(
            "registry match for %s: %s via %s.%s",
            entry.cve_id, reg_entry.label, reg_entry.table, reg_entry.name_match,
        )
        return MappedKev(
            kev=entry,
            status=MappingStatus.MAPPED,
            osquery_sql=sql,
            osquery_table=reg_entry.table,
            mapping_reason=f"Registry match: {reg_entry.label} detected via {reg_entry.table}.{reg_entry.name_column}",
            confidence="high",
            platform=reg_entry.platform,
        )

    # Step 2: Try Claude-assisted mapping if API key is available.
    if anthropic_api_key:
        try:
            cm = _get_claude_mapper()
            result = await cm.generate_mapping(
                entry,
                api_key=anthropic_api_key,
                model=anthropic_model,
            )
            if result:
                logger.info(
                    "claude-assisted mapping for %s: %s",
                    entry.cve_id, result.mapping_reason,
                )
                return result
        except Exception as exc:
            logger.warning(
                "claude mapper failed for %s: %s", entry.cve_id, exc,
            )

    # Step 3: Unmappable.
    reason = _unmappable_reason(entry)
    logger.info("unmappable: %s — %s", entry.cve_id, reason)
    return MappedKev(
        kev=entry,
        status=MappingStatus.UNMAPPABLE,
        mapping_reason=reason,
    )


def _unmappable_reason(entry: KevEntry) -> str:
    """Generate a human-readable reason why a KEV entry cannot be
    mapped to an osquery detection query."""
    vendor = entry.vendor_project.lower()
    product = entry.product.lower()

    # Network appliances and hardware.
    appliance_vendors = {
        "cisco", "fortinet", "palo alto", "juniper", "f5",
        "citrix", "ivanti", "sonicwall", "zyxel", "barracuda",
        "netgear", "d-link", "tp-link", "qnap", "synology",
    }
    for v in appliance_vendors:
        if v in vendor:
            return (
                f"Network appliance or hardware vendor ({entry.vendor_project}). "
                f"Not detectable via osquery host agent."
            )

    # SaaS / cloud products.
    if any(w in product for w in ["cloud", "saas", "online"]):
        return (
            f"Cloud or SaaS product ({entry.product}). "
            f"Not installed on endpoints."
        )

    # Mobile-only.
    if any(w in product for w in ["ios", "android", "mobile"]):
        return (
            f"Mobile platform ({entry.product}). "
            f"osquery does not run on mobile devices."
        )

    return (
        f"No curated mapping for {entry.vendor_project} {entry.product}. "
        f"Product may not be detectable via standard osquery tables, "
        f"or the mapping has not been added to the registry yet."
    )
