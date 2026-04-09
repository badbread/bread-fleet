"""Pydantic models for the backend's request/response shapes.

Every external boundary (Fleet REST API in, frontend REST API out, Claude
API in/out, audit log lines) goes through a typed model. The frontend
gets exactly what these models describe and never has to guess at the
shape of a response.

Models are split into three groups:
  - FleetHost / FleetPolicy: incoming shapes from Fleet's REST API
  - TranslatedPolicy / HostCompliance: outgoing shapes the frontend renders
  - AuditEntry: append-only audit log row
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Inbound shapes (from Fleet's REST API)
# ----------------------------------------------------------------------


class FleetPolicy(BaseModel):
    """A single policy result for a host as returned by Fleet's
    /api/latest/fleet/hosts/{id} endpoint.

    Only the fields the troubleshooter actually uses are modeled. Fleet
    returns more, the rest are ignored via Pydantic's default behavior
    of dropping unknown keys.
    """

    id: int
    name: str
    query: str
    description: Optional[str] = None
    resolution: Optional[str] = None
    response: str = Field(
        default="",
        description="'pass', 'fail', or empty string for not-yet-evaluated",
    )
    critical: bool = False
    platform: str = ""


class FleetHost(BaseModel):
    """A host as returned by Fleet's host detail endpoint."""

    id: int
    hostname: str
    uuid: str
    platform: str
    os_version: str
    status: str = Field(
        description="'online', 'offline', or 'mia' per Fleet's status taxonomy",
    )
    policies: list[FleetPolicy] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Outbound shapes (to the frontend)
# ----------------------------------------------------------------------


class Severity(str, Enum):
    """Severity tier for a translated policy failure.

    Mapped to UI color: low=blue, medium=yellow, high=orange, critical=red.
    The translator (Claude or fallback) picks the value, never the
    frontend, because severity is a domain decision not a UI decision.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TranslatedPolicy(BaseModel):
    """A failing policy after translation. This is what the frontend
    renders in the support-facing UI.

    The original policy_id is preserved so the audit log and the
    remediation registry can refer back to it, but the frontend should
    not display it to the support user (who is not expected to know
    what policy IDs mean).
    """

    policy_id: int
    policy_name: str = Field(
        description="Internal policy name, NOT shown to the support user",
    )

    # The fields below are what the user actually sees.
    summary: str = Field(
        description="1-2 plain-english sentences describing what is wrong",
    )
    impact: str = Field(
        description="1 sentence on why this matters",
    )
    fix_steps: list[str] = Field(
        description="Ordered steps a support person can walk a user through",
    )
    severity: Severity
    support_can_fix_themselves: bool = Field(
        description="True if the remediation does not need engineering",
    )
    escalate_to: Optional[str] = Field(
        default=None,
        description="If support_can_fix_themselves is False, who to escalate to",
    )

    # Remediation metadata: does this policy have an automated fix
    # registered, and if so what's its identifier?
    automated_remediation_id: Optional[str] = Field(
        default=None,
        description="Registry key for an automated fix, or None for manual-only",
    )


class HostCompliance(BaseModel):
    """The full compliance picture for one host. Returned by the
    /api/hosts/{hostname}/compliance endpoint.
    """

    hostname: str
    platform: str
    os_version: str
    status: str
    pass_count: int
    fail_count: int
    pending_count: int
    failing_policies: list[TranslatedPolicy] = Field(
        description="Only failing policies. Passing policies are not enriched",
    )
    last_checked: datetime


# ----------------------------------------------------------------------
# Remediation
# ----------------------------------------------------------------------


class RemediationOutcome(str, Enum):
    """Result of an attempted remediation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"
    REQUIRES_RECHECK = "requires_recheck"


class RemediationResponse(BaseModel):
    """Response to a remediation attempt."""

    outcome: RemediationOutcome
    message: str = Field(
        description="Human-readable status the frontend can show directly",
    )
    fleet_script_execution_id: Optional[str] = Field(
        default=None,
        description="Fleet's execution ID for the script run, for audit",
    )


# ----------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------


class AuditAction(str, Enum):
    """Categories of action that get audit-logged."""

    HOST_SEARCH = "host_search"
    HOST_COMPLIANCE_FETCH = "host_compliance_fetch"
    REMEDIATION_ATTEMPT = "remediation_attempt"
    AUDIT_QUERY = "audit_query"


class AuditEntry(BaseModel):
    """Single line in the JSONL audit log.

    The operator field is a placeholder string in the MVP because there
    is no auth. At enterprise scale this becomes the user's ID from the
    SSO session JWT.
    """

    timestamp: datetime
    operator: str
    action: AuditAction
    target_host: Optional[str] = None
    policy_id: Optional[int] = None
    outcome: Optional[str] = None
    detail: Optional[str] = None
