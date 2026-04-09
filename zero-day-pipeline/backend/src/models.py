"""Pydantic models for the Zero-Day Response Pipeline API.

Three model groups:
1. Inbound: KevEntry parsed from the CISA KEV JSON feed.
2. Mapping: MappedKev with the generated osquery SQL and status.
3. Deployment: DeployedPolicy tracking what was pushed to Fleet.
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# CISA KEV feed models
# ------------------------------------------------------------------ #

class KevEntry(BaseModel):
    """Single vulnerability from the CISA Known Exploited
    Vulnerabilities catalog."""
    cve_id: str = Field(alias="cveID")
    vendor_project: str = Field(alias="vendorProject")
    product: str
    vulnerability_name: str = Field(alias="vulnerabilityName")
    date_added: str = Field(alias="dateAdded")
    short_description: str = Field(alias="shortDescription")
    required_action: str = Field(alias="requiredAction")
    due_date: str = Field(alias="dueDate")
    known_ransomware_campaign_use: str = Field(alias="knownRansomwareCampaignUse")
    notes: str = ""

    model_config = {"populate_by_name": True}


class KevFeedResponse(BaseModel):
    """Wrapper for the feed endpoint response."""
    total: int
    entries: list[KevEntry]


# ------------------------------------------------------------------ #
# Mapping models
# ------------------------------------------------------------------ #

class MappingStatus(str, Enum):
    MAPPED = "mapped"
    CLAUDE_ASSISTED = "claude_assisted"
    UNMAPPABLE = "unmappable"


class MappedKev(BaseModel):
    """Result of mapping a KEV entry to an osquery detection query."""
    kev: KevEntry
    status: MappingStatus
    osquery_sql: Optional[str] = None
    osquery_table: Optional[str] = None
    mapping_reason: str = Field(
        description="Why this mapping was chosen or why it's unmappable",
    )
    confidence: Optional[Literal["high", "medium", "low"]] = None
    platform: str = "linux"


# ------------------------------------------------------------------ #
# Deployment models
# ------------------------------------------------------------------ #

class HostResult(BaseModel):
    """Per-host evaluation result for a deployed policy."""
    hostname: str
    status: str = Field(description="'pass', 'fail', or 'pending'")


class DeployedPolicy(BaseModel):
    """A KEV-generated policy that has been deployed to Fleet."""
    cve_id: str
    fleet_policy_id: Optional[int] = None
    policy_name: str
    osquery_sql: str
    deployed_at: str
    dry_run: bool
    host_results: list[HostResult] = []


class DeployRequest(BaseModel):
    dry_run: bool = True


class PipelineStats(BaseModel):
    """Summary statistics for the pipeline dashboard."""
    kev_total: int
    mapped: int
    claude_assisted: int
    unmappable: int
    deployed: int
