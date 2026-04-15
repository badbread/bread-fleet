"""Zero-Day Response Pipeline API.

Bridges the gap between CISA's Known Exploited Vulnerabilities catalog
and Fleet's policy-based detection. Fetches the KEV feed, maps entries
to osquery detection queries using a curated registry (with optional
Claude AI assist), and deploys the generated queries as Fleet policies.

Routes:
  GET  /healthz                         -- liveness
  GET  /api/kev/feed                    -- browse KEV entries with filters
  GET  /api/kev/{cve_id}               -- single entry detail
  POST /api/kev/{cve_id}/map           -- generate osquery SQL
  POST /api/kev/{cve_id}/deploy        -- deploy to Fleet
  GET  /api/policies                    -- deployed KEV policies
  GET  /api/policies/{policy_id}/results -- host pass/fail for a policy
  DELETE /api/policies/{policy_id}      -- remove a deployed policy
  GET  /api/stats                       -- pipeline summary
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .audit import AuditAction, AuditLogger
from .config import Settings, get_settings
from .kev_client import KevClient
from .policy_store import PolicyStore
from .models import (
    DeployedPolicy,
    DeployRequest,
    HostResult,
    KevFeedResponse,
    MappedKev,
    PipelineStats,
)
from . import mapper

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build singletons once at startup, tear down on shutdown."""
    settings = get_settings()

    app.state.kev_client = KevClient(
        feed_url=settings.kev_feed_url,
        cache_ttl=settings.kev_cache_ttl_seconds,
    )
    app.state.policy_store = PolicyStore(
        path=settings.audit_log_path.parent / "policies.json",
    )
    app.state.audit = AuditLogger(settings.audit_log_path)
    app.state.settings = settings

    logger.info("zero-day pipeline started")
    yield

    await app.state.kev_client.close()


app = FastAPI(
    title="Zero-Day Response Pipeline",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


# ------------------------------------------------------------------ #
# Dependency injection helpers
# ------------------------------------------------------------------ #

def _kev(request: Request) -> KevClient:
    return request.app.state.kev_client

def _store(request: Request) -> PolicyStore:
    return request.app.state.policy_store

def _audit(request: Request) -> AuditLogger:
    return request.app.state.audit

def _settings(request: Request) -> Settings:
    return request.app.state.settings


# ------------------------------------------------------------------ #
# Routes
# ------------------------------------------------------------------ #

@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/kev/feed", response_model=KevFeedResponse)
async def kev_feed(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    product: Optional[str] = Query(default=None, min_length=1),
    ransomware_only: bool = Query(default=False),
    kev: KevClient = Depends(_kev),
    audit: AuditLogger = Depends(_audit),
):
    """Browse the CISA KEV catalog with optional filters."""

    entries = await kev.filter_feed(
        days=days, product=product, ransomware_only=ransomware_only,
    )
    audit.record(
        AuditAction.KEV_FEED_POLL,
        detail=f"fetched {len(entries)} entries (days={days}, product={product})",
    )
    return KevFeedResponse(total=len(entries), entries=entries)


@app.get("/api/kev/{cve_id}", response_model=MappedKev)
async def kev_detail(cve_id: str, kev: KevClient = Depends(_kev), settings: Settings = Depends(_settings)):
    """Look up a single KEV entry and return its mapping status."""

    entry = await kev.get_entry(cve_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found in KEV feed")

    result = await mapper.map_entry(
        entry,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )
    return result


@app.post("/api/kev/{cve_id}/map", response_model=MappedKev)
async def map_kev(cve_id: str, kev: KevClient = Depends(_kev), audit: AuditLogger = Depends(_audit), settings: Settings = Depends(_settings)):
    """Generate an osquery detection query for a KEV entry."""

    entry = await kev.get_entry(cve_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found in KEV feed")

    result = await mapper.map_entry(
        entry,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )
    audit.record(
        AuditAction.POLICY_MAPPED,
        cve_id=cve_id,
        detail=f"status={result.status.value}, reason={result.mapping_reason}",
    )
    return result


@app.post("/api/kev/{cve_id}/deploy", response_model=DeployedPolicy)
async def deploy_kev(
    cve_id: str,
    body: DeployRequest,
    kev: KevClient = Depends(_kev),
    store: PolicyStore = Depends(_store),
    audit: AuditLogger = Depends(_audit),
    settings: Settings = Depends(_settings),
):
    """Deploy a KEV detection query as a Fleet policy.

    Set dry_run=true to preview the policy without deploying it.
    In the demo, deployment is simulated with a local policy store
    and synthetic host results. In production, this calls Fleet's
    POST /api/latest/fleet/global/policies endpoint.
    """

    entry = await kev.get_entry(cve_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found in KEV feed")

    mapped = await mapper.map_entry(
        entry,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )
    if not mapped.osquery_sql:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot deploy: {mapped.mapping_reason}",
        )

    policy_name = f"Zero-Day: {cve_id} — {entry.product}"
    now = datetime.now(timezone.utc).isoformat()

    if body.dry_run:
        deployed = DeployedPolicy(
            cve_id=cve_id,
            policy_name=policy_name,
            osquery_sql=mapped.osquery_sql,
            deployed_at=now,
            dry_run=True,
        )
        audit.record(
            AuditAction.POLICY_DEPLOYED,
            cve_id=cve_id,
            detail=f"dry run: {policy_name}",
        )
        return deployed

    try:
        deployed = store.deploy(
            cve_id=cve_id,
            policy_name=policy_name,
            osquery_sql=mapped.osquery_sql,
            platform=mapped.platform,
        )
    except ValueError as exc:
        # A policy for this CVE is already deployed. Return 409 so the
        # frontend can surface a "already deployed" message rather than
        # silently creating a duplicate entry.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    audit.record(
        AuditAction.POLICY_DEPLOYED,
        cve_id=cve_id,
        detail=f"deployed as policy {deployed.fleet_policy_id}: {policy_name}",
    )
    return deployed


@app.get("/api/policies", response_model=list[DeployedPolicy])
async def list_deployed(store: PolicyStore = Depends(_store)):
    """List policies deployed through this pipeline."""
    return store.list_policies()


@app.get("/api/policies/{policy_id}/results", response_model=list[HostResult])
async def policy_results(policy_id: int, store: PolicyStore = Depends(_store)):
    """Get per-host pass/fail results for a deployed policy."""
    results = store.get_results(policy_id)
    if results is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return results


@app.delete("/api/policies/{policy_id}")
async def delete_policy(policy_id: int, store: PolicyStore = Depends(_store), audit: AuditLogger = Depends(_audit)):
    """Remove a deployed policy."""
    if not store.delete(policy_id):
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    audit.record(
        AuditAction.POLICY_DELETED,
        detail=f"deleted policy {policy_id}",
    )
    return {"status": "deleted", "policy_id": policy_id}


@app.get("/api/stats", response_model=PipelineStats)
async def stats(kev: KevClient = Depends(_kev), store: PolicyStore = Depends(_store), settings: Settings = Depends(_settings)):
    """Summary statistics: how many KEV entries are mappable."""

    entries = await kev.fetch_feed()

    mapped = 0
    claude_assisted = 0
    unmappable = 0

    for entry in entries:
        result = await mapper.map_entry(
            entry,
            # Don't call Claude for stats — just check the registry.
            anthropic_api_key="",
            anthropic_model=settings.anthropic_model,
        )
        if result.status.value == "mapped":
            mapped += 1
        elif result.status.value == "claude_assisted":
            claude_assisted += 1
        else:
            unmappable += 1

    return PipelineStats(
        kev_total=len(entries),
        mapped=mapped,
        claude_assisted=claude_assisted,
        unmappable=unmappable,
        deployed=len(store.list_policies()),
    )
