"""Security Posture Dashboard API.

Serves fleet-wide compliance data that Fleet's built-in UI does not
provide: historical trends, weighted risk scoring, and executive-ready
aggregation. The demo serves synthetic data from seed_data.json; in
production, the data layer would be Fleet's REST API with periodic
snapshots in Postgres.

Routes:
  GET /api/healthz                        -- liveness
  GET /api/posture/summary                -- fleet health score + platform split
  GET /api/posture/trend?days=30          -- daily compliance trend with events
  GET /api/posture/policies               -- policies ranked by failure rate
  GET /api/posture/policies/{id}/devices  -- devices failing a specific policy
  GET /api/posture/devices?sort=risk      -- devices ranked by risk score
"""

import logging

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    DeviceRisk,
    PolicyDevice,
    PolicyRanking,
    PostureSummary,
    TrendPoint,
)
from . import synthetic
from .config import Settings

settings = Settings()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Security Posture Dashboard",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

# CORS for local development. In the portal deployment, the portal
# nginx handles same-origin routing so CORS is unnecessary. This
# fallback keeps `npm run dev` working against the backend directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/posture/summary", response_model=PostureSummary)
async def posture_summary():
    """Fleet-wide health score and platform breakdown.

    The health score is severity-weighted: a critical policy failure
    (like missing disk encryption) counts 4x more than a low-severity
    one (like Bluetooth sharing). This is the number a CISO cares
    about, not a raw pass/fail count.
    """
    return synthetic.get_summary()


@app.get("/api/posture/trend", response_model=list[TrendPoint])
async def posture_trend(days: int = Query(default=30, ge=1, le=90)):
    """Daily compliance scores over time.

    Fleet has no concept of historical compliance. It shows the current
    state. This endpoint provides the time-series view that answers
    "are we improving?" and "what happened on March 23rd that caused
    the dip?" -- questions Fleet cannot answer.
    """
    return synthetic.get_trend(days)


@app.get("/api/posture/policies", response_model=list[PolicyRanking])
async def posture_policies():
    """Policies ranked by fleet-wide failure rate.

    Fleet shows per-policy pass/fail counts, but does not rank them
    by failure rate or weight them by severity. This endpoint surfaces
    "OS version current fails on 28% of the fleet (high severity)"
    ahead of "NTP configured fails on 3% (low severity)" so the team
    knows where to focus remediation effort.
    """
    return synthetic.get_policies_ranked()


@app.get(
    "/api/posture/policies/{policy_id}/devices",
    response_model=list[PolicyDevice],
)
async def policy_devices(policy_id: int):
    """Devices failing a specific policy. Drill-down from the ranked
    policy list to see exactly which devices need attention."""
    return synthetic.get_policy_devices(policy_id)


@app.get("/api/posture/devices", response_model=list[DeviceRisk])
async def posture_devices():
    """All devices ranked by weighted risk score.

    The risk score sums the severity weights of all failing policies on
    a device. A device failing two critical policies (weight 4 each)
    scores 8, higher than one failing four low policies (weight 1 each,
    score 4). This is the "problem children" list that drives
    remediation prioritization -- a view Fleet does not provide.
    """
    return synthetic.get_devices_by_risk()
