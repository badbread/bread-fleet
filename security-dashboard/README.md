# Security Posture Dashboard

Fleet-wide compliance visibility that Fleet's built-in UI does not
provide: historical trends, severity-weighted scoring, cross-platform
comparison, and risk concentration analysis.

## What it solves

Fleet shows the current state per host and per policy. It does not
answer:

- **Are we improving?** No historical data, no trend line, no way to
  correlate a compliance dip with the policy deployment that caused it.
- **What actually matters?** All policy failures look the same. A
  missing disk encryption (critical) is indistinguishable from a
  Bluetooth sharing misconfiguration (low).
- **Where is risk concentrated?** No ranked "worst devices" view,
  no cross-platform comparison, no way to find the 10 devices that
  account for the most risk.

This dashboard adds those views. It uses synthetic data shaped to
look like a 150-device enterprise fleet because the demo Fleet
instance has two enrolled hosts, which is not enough to tell a
fleet-wide story.

## Architecture

```
+------------------+        +------------------+
|                  |        |                  |
|  Browser         | -----> |  Dashboard       |
|  (React +        | <----- |  backend         |
|   Recharts)      |        |  (FastAPI)       |
|                  |        |                  |
+------------------+        +--------+---------+
                                     |
                            +--------v---------+
                            |  synthetic.py    |
                            |  seed_data.json  |
                            |  (in production: |
                            |  Fleet API +     |
                            |  Postgres)       |
                            +------------------+
```

The backend has no external dependencies in the MVP. It generates a
deterministic 152-device fleet from seed data at startup and serves
it through five API endpoints. In production, `synthetic.py` is
replaced by a scheduled aggregation job that polls Fleet's REST API
and stores snapshots in Postgres.

## Synthetic data design

The seed data is not random noise. It tells a story:

- **~150 devices** across three fleet segments: 100 macOS laptops
  (engineering), 30 Ubuntu servers (infrastructure), 20 Windows
  desktops (corporate), plus 2 real Fleet hosts.
- **15 policies** with severity weights (critical 4x, high 3x,
  medium 2x, low 1x) mirroring real CIS benchmarks.
- **Failure rates shaped to real-world patterns.** OS currency
  fails on ~28% of the fleet (patch lag). Disk encryption fails
  on ~4% (enforced early). SSH key-only auth fails on ~22%
  (recently deployed policy).
- **30-day historical arc** showing compliance improving from 72%
  to 87%: bulk remediation push on day 8, new policy dip on day
  14, recovery by day 30. Annotated events explain each inflection.
- **Deterministic generation** using hostname+policy hashes so the
  same device always fails the same policies across page loads.

The portal landing page labels this module as "Augmented data" and
the dashboard footer states the data source explicitly.

See [ADR-0007](../docs/adr/0007-security-posture-dashboard.md) for
the full design rationale and alternatives considered.

## Dashboard sections

1. **Health Score** -- severity-weighted fleet compliance percentage
2. **Platform Breakdown** -- per-platform device counts and scores
3. **Compliance Trend** -- 30-day line chart with event annotations
4. **Top Failing Policies** -- ranked by failure rate, colored by severity
5. **Risk Table** -- top 10 devices by weighted risk score
6. **Policy Coverage** -- rollout progress bars per policy

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness probe |
| GET | `/api/posture/summary` | Fleet health score + platform split |
| GET | `/api/posture/trend?days=30` | Daily compliance trend with events |
| GET | `/api/posture/policies` | Policies ranked by failure rate |
| GET | `/api/posture/policies/{id}/devices` | Devices failing a specific policy |
| GET | `/api/posture/devices` | Devices ranked by risk score |

## Running it locally

```
docker compose up -d
```

Frontend: `http://localhost:5174`. Backend: `http://localhost:8089`.
No `.env` file needed -- the dashboard has no external dependencies.

## At enterprise scale

ADR-0007 covers the deltas in detail. The summary:

- Synthetic data module is replaced by a scheduled Fleet API
  aggregation job writing to Postgres.
- Retention: daily snapshots for 90 days, weekly rollups for 1 year.
- RBAC gated behind the same Cloudflare Access policy as the portal.
- Threshold alerting to Slack/PagerDuty when health score drops
  below a target.
- Per-team breakdown using Fleet's team-scoped API tokens.
