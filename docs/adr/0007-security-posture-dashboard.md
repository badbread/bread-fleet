# ADR-0007: Security Posture Dashboard with synthetic data

## Status

Accepted

## Context

The Compliance Troubleshooter (ADR-0005) solves the per-device
question: "Why is this device non-compliant and how do we fix it?"
That is the support staff's view. Leadership and the security team
need a different view: "How healthy is our fleet overall, and is it
getting better or worse?"

Fleet's built-in UI shows per-policy pass/fail counts and per-host
detail. It does not provide:

- Historical compliance data. Fleet shows the current state. There
  is no time-series, no "are we improving?", no way to correlate a
  compliance dip with the policy deployment that caused it.
- Severity-weighted scoring. Fleet treats all policy failures
  equally. A device missing disk encryption (critical, data breach
  risk) looks the same as one with Bluetooth sharing enabled (low,
  marginal attack surface). Weighted scoring surfaces what actually
  matters.
- Cross-platform comparison. Fleet lets you filter hosts by
  platform but does not present macOS vs Linux vs Windows compliance
  side by side.
- Risk concentration. Fleet has no ranked "worst devices" view.
  There is no way to answer "which 10 devices account for the most
  risk?" without manually inspecting each host.

The demo Fleet instance has two enrolled Linux hosts. That is not
enough data to demonstrate fleet-wide posture visibility. The
dashboard uses synthetic data shaped to look like a 150-device
enterprise fleet.

## Decision

Build a Security Posture Dashboard as a separate module in the
portal, served at `/dashboard/`. The dashboard adds the four
capabilities listed above using a synthetic dataset designed to tell
a realistic compliance story.

**Synthetic data design:**

- ~150 devices across three fleet segments: 100 macOS laptops
  (engineering), 30 Ubuntu servers (infrastructure), 20 Windows
  desktops (corporate). Two real Fleet hosts (lab-linux-01, lab-linux-02)
  are included in the dataset.
- 15 policies with severity weights (critical 4x, high 3x, medium
  2x, low 1x). Policy selection mirrors real CIS benchmarks: disk
  encryption, firewall, OS currency, SSH auth, Gatekeeper, auditd,
  screen lock, automatic updates, SIP, and others.
- Failure rates shaped to match real-world patterns. OS currency
  fails on ~28% of the fleet (patch lag is universal). Disk
  encryption fails on ~4% (usually enforced early). SSH key-only
  auth fails on ~22% (recently deployed policy, teams still
  transitioning).
- 30-day historical snapshots showing a compliance improvement arc:
  72% baseline, bulk remediation push on day 8, new policy dip on
  day 14, recovery to 87% by day 30. Annotated events on the
  timeline explain each inflection point.
- Deterministic generation using hostname+policy hashes so the same
  device always fails the same policies across page loads. No random
  noise.

**The portal landing page is honest about the data.** The dashboard
card says "Augmented data" and the footer reads "Data: synthetic
(augmented from real Fleet policies to ~152 devices)."

**Tech stack:** Same as the troubleshooter (React 18 + Vite +
Tailwind + FastAPI) plus Recharts for charting. No Claude API
integration; this module is data visualization, not AI translation.

## Alternatives Considered

1. **Pull aggregate data from the real Fleet API.** Fleet does offer
   `/api/latest/fleet/hosts` and `/api/latest/fleet/policies` with
   pass/fail counts. Two hosts produce a chart with two data points.
   The visual story is empty and the dashboard looks broken rather
   than impressive. Rejected because the demo needs volume to
   demonstrate the concept.

2. **Use Fleet's API for real data and pad with synthetic devices.**
   Mixing real and fake data in the same view creates a confusing
   "which of these are real?" question for the viewer. Cleaner to
   keep the troubleshooter as the "real data" module and the
   dashboard as the "augmented data" module, with honest labeling on
   each.

3. **Skip the dashboard entirely.** The troubleshooter already shows
   per-device compliance. But the per-device view is support-facing.
   A CPE team also needs fleet-wide visibility for leadership
   reporting, remediation prioritization, and trend analysis. Skipping
   the dashboard leaves that gap unaddressed in the project.

4. **Use a third-party BI tool (Grafana, Metabase) instead of a
   custom React app.** Faster to stand up, but the value is
   in showing the purpose-built UI and the thinking behind what a CPE
   dashboard should surface. A generic BI dashboard doesn't
   demonstrate the same understanding of the problem space.

## Tradeoffs

- **The dashboard runs on fake data.** The portal landing page is
  honest about this, but a skeptical viewer might discount the module
  as "just a chart over a JSON file." The counterargument: the seed
  data itself is the artifact. It shows understanding of realistic
  compliance distributions, severity weighting, and what a fleet
  actually looks like at scale.

- **Duplicate Tailwind config.** The dashboard and troubleshooter
  share the same design tokens but each has its own
  tailwind.config.js. In a production monorepo, this would be a
  shared package. For the MVP, duplication is cheaper than the build
  complexity of a shared config.

- **No real historical data pipeline.** The trend chart comes from a
  static JSON array, not a real scheduled aggregation job. The
  architecture supports replacing the synthetic module with a real
  data source (the API shapes are identical), but the pipeline itself
  is not built.

## At Enterprise Scale

The synthetic data module goes away. In its place:

- **Scheduled aggregation job** polls Fleet's REST API every 15
  minutes. Each poll snapshots per-policy pass/fail counts and
  per-host policy results into a Postgres time-series table. This is
  the source of truth for the trend chart.

- **Fleet API endpoints used:** `GET /api/latest/fleet/hosts`
  (paginated, with policy results) and
  `GET /api/latest/fleet/policies` (aggregate counts). Both are
  already authenticated the same way the troubleshooter's client
  authenticates.

- **Data retention policy:** keep daily snapshots for 90 days,
  weekly rollups for 1 year. Older data is aggregated to monthly.
  Total storage is trivial (a few MB per month for a 1,000-device
  fleet).

- **RBAC:** the dashboard is read-only, but not everyone should see
  it. Gate access behind the same Cloudflare Access policy that
  protects the portal, with an additional group claim for
  "security-team" or "cpe-leads."

- **Alerting:** threshold-based alerts when the fleet health score
  drops below a configurable target (e.g., 85%). Route to Slack or
  PagerDuty. The dashboard shows the alert history on the trend
  chart as additional event annotations.

- **Per-team breakdown:** with Fleet's team-scoped API tokens, the
  dashboard could show compliance by team (engineering vs corporate
  vs infrastructure) instead of just by platform. This requires
  Fleet Premium or a mapping table from hostname patterns to team
  labels.
