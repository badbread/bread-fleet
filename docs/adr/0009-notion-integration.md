# ADR-0009: Live Notion integration for compliance audit trail

## Status

Accepted

## Context

The Compliance Troubleshooter logs every investigation and
remediation action to a JSONL audit file. That file is correct and
complete, but nobody outside the engineering team will ever look at
it. Support teams, security leadership, and CPE managers live in
tools like Notion, not in terminal sessions tailing JSONL.

The question: where does the compliance audit trail live so the
people who need it can actually use it?

## Decision

Connect the Compliance Troubleshooter to the Notion API. Every
compliance check and remediation action pushes a row to a shared
Notion database in real time. The database is structured as a
remediation log with columns for device, platform, failed policy,
severity, root cause (plain English), remediation action, status,
who resolved it, timestamp, and a link back to the troubleshooter.

**Why Notion specifically:** The team this project is aimed at
already uses Notion as their primary knowledge and workflow tool.
Meeting users where they already work is a core CPE principle.
Pushing compliance data into Notion means security reviews, support
handoffs, and management reporting all happen in the same tool
without context-switching.

**Database schema:**

| Column | Type | Why it exists |
|--------|------|---------------|
| Device | Title | Primary identifier. Support searches by hostname. |
| Platform | Select | Enables filtering by fleet segment (macOS vs Linux). |
| Failed Policy | Rich text | Plain-English policy name, no CIS IDs. |
| Severity | Select | Color-coded for visual scanning. Drives triage priority. |
| Root Cause | Rich text | Claude-translated explanation. No SQL, no osquery. |
| Remediation | Rich text | What was done or what needs to be done. |
| Status | Select | Fixed/Pending/Escalated/In Progress. The workflow state. |
| Resolved By | Rich text | Attribution: support, automation, or engineering. |
| Timestamp | Date | When the event occurred. Enables time-based filtering. |
| Source | URL | Deep link back to the troubleshooter for this host. |

**Sync strategy:** Direct API call on each compliance event.
Not batch, not webhook, not polling. Each compliance check and each
remediation action fires a non-blocking POST to Notion's API. The
call is fire-and-forget (asyncio.create_task) so it never slows
down the troubleshooter's response to the frontend. If the Notion
API is down or rate-limited, the failure is logged and swallowed.
The JSONL audit log remains the authoritative record; Notion is the
convenience view.

**Seed data:** A one-shot CLI script populates the database with
real policy failures from the Fleet API plus realistic simulated
historical entries showing three weeks of support activity. The
simulated entries tell a story: initial CIS rollout, bulk
remediation, new policy deployment causing a compliance dip,
ongoing triage. The mix of statuses (Fixed, Pending, Escalated,
In Progress) and resolvers (support, automation, engineering) makes
the database look like an active operational tool, not a static
demo.

## Alternatives Considered

1. **Slack channel integration.** Push compliance events to a Slack
   channel. Rejected because Slack messages are ephemeral and
   unsearchable after a few weeks. A Notion database is persistent,
   filterable, and sortable -- properties that matter for compliance
   audit trails.

2. **Google Sheets.** Familiar, sortable, filterable. Rejected
   because the target audience uses Notion, not Sheets. Meeting
   users where they are is the point.

3. **Custom dashboard with Postgres.** The Security Posture
   Dashboard already exists for fleet-wide visualization. A
   separate audit database would duplicate effort. Notion serves the
   "individual event log" use case that the dashboard's aggregate
   views do not.

4. **Keep the JSONL file only.** The file is correct and complete
   but invisible to non-engineers. A compliance audit trail that
   nobody reads is a compliance audit trail that doesn't exist.

## Tradeoffs

- **Notion API rate limit (3 req/s).** A compliance check that
  returns 10 failing policies fires 10 Notion API calls. At 3/s
  that's ~3 seconds of background work. For the demo fleet (4
  hosts, ~20 policies) this is fine. At enterprise scale with
  hundreds of concurrent compliance checks, the sync would need
  batching or a queue.

- **Cloudflare WAF sensitivity.** Notion's API sits behind
  Cloudflare, which aggressively blocks rapid sequential POST
  requests from the same IP. The seed script handles this with
  backoff and retry, but it makes initial population slow (~2
  minutes for 30 entries). Live sync is unaffected because
  individual compliance checks produce 1-5 API calls, well under
  the detection threshold.

- **Duplicate entries.** If a user checks compliance for the same
  host twice, the same failing policies appear as new Notion rows.
  The demo accepts this. At scale, an idempotency key
  (timestamp + hostname + policy_name hash) would deduplicate.

- **No bidirectional sync.** If someone edits the Status column
  in Notion (e.g., marks a Pending entry as Fixed), the
  troubleshooter doesn't know about it. The Notion database is
  write-only from the troubleshooter's perspective. Bidirectional
  sync would require Notion webhooks and a reconciliation layer.

## At Enterprise Scale

- **Queue-based sync.** Replace fire-and-forget API calls with a
  message queue (SQS, Redis Streams). A dedicated worker consumes
  events and pushes to Notion with retry and backoff, decoupling
  the troubleshooter's latency from Notion's availability.

- **Idempotency.** Each event gets a deterministic key
  (SHA256 of timestamp + hostname + policy_name). The worker
  checks Notion's database for an existing page with that key
  before creating a new one.

- **Bidirectional sync.** Notion webhooks (currently in beta)
  notify the troubleshooter when a row's Status changes. The
  troubleshooter updates the JSONL audit log to match, keeping
  both sources consistent.

- **Workspace-level integration.** The demo uses a page-level
  Notion integration. At scale, the integration would be
  workspace-level so multiple databases (compliance log, incident
  tracker, policy exception register) share one auth token.

- **Retention and archival.** Notion databases have no built-in
  archival. A scheduled job would move entries older than 90 days
  to an archive database or export to Postgres for long-term
  retention.

- **RBAC.** The Notion page sharing model controls who sees the
  compliance log. At scale, the database would be shared with
  specific Notion groups (security team, support leads, CPE
  managers) rather than published to the web.
