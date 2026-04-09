"""FastAPI application entry.

Defines the HTTP routes the frontend talks to and wires up the
fleet client, translator, audit logger, and remediation registry as
process-lifetime singletons.

The whole API surface is intentionally small:

  GET  /healthz                                liveness
  GET  /api/hosts/search?q={query}             search hosts in Fleet
  GET  /api/hosts/{hostname}/compliance        full compliance view, translated
  POST /api/hosts/{hostname}/remediate         run a registered remediation
  GET  /api/audit?host=&limit=                 read recent audit entries

Why no /openapi or /docs route customization: FastAPI auto-generates
both at /docs and /redoc and they're useful as a sanity check during
development. They are not auth-gated; in the at-scale build they
would be behind the same SSO as the rest of the tool.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .audit import AuditLogger
from .config import Settings, get_settings
from .fleet_client import FleetClient, FleetClientError, failing_policies, passing_count, pending_count
from .models import (
    AuditAction,
    AuditEntry,
    HostCompliance,
    RemediationOutcome,
    RemediationResponse,
)
from .remediation import get_handler
from .translator import Translator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ----------------------------------------------------------------------
# Lifespan: build the singletons once at startup, tear them down at exit
# ----------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan handler. Builds the singletons.

    The components are kept on app.state so dependency injection can
    grab them via a per-request Depends rather than via a module-level
    global. This makes the components swappable in tests.
    """
    settings = get_settings()
    app.state.settings = settings
    app.state.fleet_client = FleetClient(settings)
    app.state.translator = Translator(settings)
    app.state.audit = AuditLogger(settings)
    logger.info(
        "compliance-troubleshooter starting (fleet=%s, claude=%s)",
        settings.fleet_api_url,
        "enabled" if settings.anthropic_api_key else "static fallback",
    )
    try:
        yield
    finally:
        await app.state.fleet_client.aclose()
        logger.info("compliance-troubleshooter shutting down")


app = FastAPI(
    title="Compliance Troubleshooter",
    description="Plain-English translation layer for Fleet compliance findings.",
    version="0.1.0",
    lifespan=lifespan,
)


# CORS: only allow the configured frontend origin. The frontend talks
# to this backend across origins because they run on different ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().cors_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# Dependency injection helpers
# ----------------------------------------------------------------------
#
# Each helper pulls a singleton off app.state. Tests override these to
# substitute fakes; production code never calls them directly.


def _settings_dep() -> Settings:
    return app.state.settings


def _fleet_dep() -> FleetClient:
    return app.state.fleet_client


def _translator_dep() -> Translator:
    return app.state.translator


def _audit_dep() -> AuditLogger:
    return app.state.audit


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Unauthenticated liveness check used by the Compose healthcheck."""
    return {"status": "ok"}


@app.get("/api/hosts/search")
async def search_hosts(
    q: str = Query(..., min_length=1, description="Hostname substring"),
    fleet: FleetClient = Depends(_fleet_dep),
    audit: AuditLogger = Depends(_audit_dep),
) -> dict:
    """Search Fleet for hosts matching a hostname substring.

    The frontend uses this for the search-as-you-type box at the top of
    the main view. Returns lightweight metadata only; the full
    compliance view is fetched separately when the user picks a host.
    """
    audit.record(
        action=AuditAction.HOST_SEARCH,
        target_host=q,
        detail=f"query={q}",
    )
    try:
        hosts = await fleet.search_hosts(q)
    except FleetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"hosts": hosts}


@app.get("/api/hosts/{hostname}/compliance", response_model=HostCompliance)
async def host_compliance(
    hostname: str,
    fleet: FleetClient = Depends(_fleet_dep),
    translator: Translator = Depends(_translator_dep),
    audit: AuditLogger = Depends(_audit_dep),
) -> HostCompliance:
    """Fetch a host's full compliance view, translated.

    Pulls the host from Fleet, walks every policy result, and runs the
    failing ones through the translator. Passing policies are NOT
    enriched because the support user only ever needs to know about
    failures: the count of passing policies is shown in the summary.
    """
    audit.record(
        action=AuditAction.HOST_COMPLIANCE_FETCH,
        target_host=hostname,
    )
    try:
        host = await fleet.get_host_detail(hostname)
    except FleetClientError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fails = failing_policies(host)
    translated = []
    for policy in fails:
        try:
            t = await translator.translate(
                policy=policy,
                host_platform=host.platform,
                host_os_version=host.os_version,
            )
        except Exception as exc:
            # Translator failures are non-fatal; show a generic message
            # for that one policy and keep going so the rest of the
            # findings still render.
            logger.error("translator error for %s: %s", policy.name, exc)
            from .models import Severity, TranslatedPolicy

            t = TranslatedPolicy(
                policy_id=policy.id,
                policy_name=policy.name,
                summary=(
                    "This finding could not be translated. The Compliance "
                    "Troubleshooter is having trouble reaching its "
                    "translation backend."
                ),
                impact=(
                    "The finding still exists in Fleet and engineering "
                    "can investigate it directly. Support cannot self-"
                    "serve this one until the translator is healthy."
                ),
                fix_steps=[
                    "Try again in a minute. If it keeps happening, "
                    "escalate to engineering and mention that the "
                    "translation layer is failing.",
                ],
                severity=Severity.MEDIUM,
                support_can_fix_themselves=False,
                escalate_to="on-call CPE engineer",
                automated_remediation_id=None,
            )
        translated.append(t)

    return HostCompliance(
        hostname=host.hostname,
        platform=host.platform,
        os_version=host.os_version,
        status=host.status,
        pass_count=passing_count(host),
        fail_count=len(fails),
        pending_count=pending_count(host),
        failing_policies=translated,
        last_checked=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )


@app.post(
    "/api/hosts/{hostname}/remediate/{remediation_id}",
    response_model=RemediationResponse,
)
async def remediate(
    hostname: str,
    remediation_id: str,
    fleet: FleetClient = Depends(_fleet_dep),
    audit: AuditLogger = Depends(_audit_dep),
) -> RemediationResponse:
    """Run a registered remediation against a host.

    The remediation_id is one of the keys in remediation.REGISTRY. The
    frontend gets these IDs from the TranslatedPolicy.automated_remediation_id
    field, so it should never POST a key that isn't registered.

    Audit log writes happen before AND after the remediation runs so
    even a panic mid-remediation leaves the attempt visible.
    """
    handler = get_handler(remediation_id)
    if handler is None:
        audit.record(
            action=AuditAction.REMEDIATION_ATTEMPT,
            target_host=hostname,
            outcome="not_registered",
            detail=remediation_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"No remediation registered with id '{remediation_id}'",
        )

    # Look up the host first so we have the host_id for the script API.
    try:
        host = await fleet.get_host_detail(hostname)
    except FleetClientError as exc:
        audit.record(
            action=AuditAction.REMEDIATION_ATTEMPT,
            target_host=hostname,
            outcome="host_lookup_failed",
            detail=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Pre-execution audit so an interrupted run still leaves a trail.
    audit.record(
        action=AuditAction.REMEDIATION_ATTEMPT,
        target_host=hostname,
        outcome="started",
        detail=remediation_id,
    )

    response = await handler(fleet, host.id)

    # Post-execution audit with the actual outcome.
    audit.record(
        action=AuditAction.REMEDIATION_ATTEMPT,
        target_host=hostname,
        outcome=response.outcome.value,
        detail=f"{remediation_id}: {response.message[:200]}",
    )

    return response


@app.get("/api/audit", response_model=list[AuditEntry])
async def read_audit(
    host: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    audit: AuditLogger = Depends(_audit_dep),
) -> list[AuditEntry]:
    """Read recent audit log entries, optionally filtered by host.

    Used by the frontend's audit panel for the in-context "what
    happened to this host recently?" view. The audit log itself is
    NOT part of the user-facing translation surface; this endpoint
    returns the raw entries.
    """
    audit.record(
        action=AuditAction.AUDIT_QUERY,
        target_host=host,
        detail=f"limit={limit}",
    )
    return audit.read_recent(host=host, limit=limit)
