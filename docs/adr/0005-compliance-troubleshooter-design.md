# ADR-0005: Compliance Troubleshooter design

## Status

Accepted

## Context

The first net-new module on top of the Fleet substrate is a tool
that translates Fleet compliance findings into plain English for
support staff and offers one-click remediation paths where
automation is safe. The audience is the support team at a
software company: smart, capable, but not engineers, and not
expected to read SQL or reason about osquery tables.

The Fleet UI itself is built for the CPE team. Every screen in
Fleet assumes the operator can read the underlying queries,
understand the policy IDs, and reason about what each table
returns. That's correct for the team that writes Fleet
configuration, but it pushes every support ticket up the
escalation chain because nobody on support can self-serve a
finding.

The decision space included how to deliver translations
(prebuilt mapping vs LLM), what stack to build the tool on
(framework choices), how to handle the remediation surface
(generic vs per-policy), how to log auditability, and how much
deployment ceremony to bring along for an MVP.

## Decision

Build the tool as a small two-tier web application running as
its own Docker Compose stack alongside the Fleet deployment.

**Backend:** FastAPI (Python 3.12), with the `anthropic` SDK
for the translation layer and `httpx` for talking to Fleet's
REST API. Audit log writes to a JSONL file. No database. The
service is stateless apart from the audit log file.

**Frontend:** React 18 + Vite + Tailwind CSS. One main view: a
host search bar at the top, a host detail panel below it, and
a per-policy card list with translated text and remediation
buttons.

**Translation layer:** Claude API via the official SDK, with a
structured-output prompt template that returns JSON the frontend
can render directly. A static fallback dict covers the 12 known
CIS policies from `gitops/default.yml`, so the MVP runs without
an API key. The fallback is also useful as a regression-test
dataset against drift in Claude's outputs over time.

**Remediation:** A per-policy remediation registry. Each entry
maps a policy ID to either an automated handler (executes a
shell script via Fleet's `/api/latest/fleet/scripts/run/sync`
endpoint) or a manual handler (returns step-by-step instructions
the support person can walk a user through). The MVP ships with
one fully automated path (`auditd_install`) and the rest as
manual stubs with clear "automation pending" messaging.

**Audit log:** JSONL append-only file at `audit/troubleshooter.jsonl`,
mounted as a volume on the backend container. Every API call
gets a log line: timestamp, operator (placeholder string until
auth lands), action, target host, policy id, outcome.

**No auth in the MVP.** Single-operator localhost-only. The
auth-shaped hole is documented as the most important missing
piece in the at-scale section of this ADR.

## Alternatives Considered

1. **Hardcoded translation dict, no LLM.** Build a static
   mapping from policy_id -> plain-english string and skip the
   Claude integration. Rejected because it does not scale: a new
   policy added to gitops/default.yml requires a code change to
   add its translation, and the translations cannot adapt to the
   per-host context (a finding on Bob's macOS laptop reads
   differently than the same finding on a Linux server). The
   LLM call adds latency and cost that are real but acceptable
   for support-volume traffic, and the static fallback covers
   the cost-sensitive case.

2. **Express + Node.js backend.** A single-language stack with
   the React frontend. Rejected because the rest of this repo
   is Python-flavored (apply.sh shell, gitops YAML, future
   zero-day pipeline almost certainly Python), and a Python
   backend keeps the language footprint coherent. CPE-team
   tooling tends Python-heavy in practice; matching that signal
   matters for the portfolio.

3. **Material UI for the frontend.** Faster to build, more
   components out of the box. Rejected because a generic
   Material app looks like every other Material app and signals
   "I scaffolded this, I didn't design it." Tailwind forces
   intentional layout choices and produces a smaller bundle.

4. **Postgres for the audit log.** The right answer at scale.
   Rejected for the MVP because adding a database to the stack
   requires a schema migration story, a backup story, and a
   container that has to start before the backend, all of which
   distract from the actual point of the tool. JSONL covers the
   demo and can be replaced behind a thin abstraction without
   rewriting the rest of the backend.

5. **Server-Sent Events or WebSocket for re-check.** Would let
   the UI auto-refresh after a remediation completes. Rejected
   because polling-on-button-click is the explicit MVP behavior,
   and SSE/WS adds connection lifecycle complexity. The
   operator clicking "Re-check" is not a UX flaw; it is a
   deliberate "did the fix actually work?" prompt that survives
   the move to enterprise scale.

6. **No remediation surface at all, just translation.** Build a
   read-only viewer. Rejected because the entire ticket-volume
   reduction story depends on support being able to fix things,
   not just understand them. Read-only is half the value at most
   of the cost.

## Tradeoffs

- **Single Claude API key for all translations.** No per-user
  rate limiting, no per-tenant prompt isolation. Acceptable for
  a single-operator MVP, blocking for any multi-tenant deploy.
- **Static fallback can drift from the live policy set.** Adding
  a new CIS policy to gitops/default.yml does NOT automatically
  add a fallback entry. A CI check would catch this; not in
  scope for the MVP.
- **One remediation works end to end, the rest are stubs.** The
  demo proves the architecture, not the breadth. A reviewer
  who tries to fix a non-auditd policy will get an honest
  "automation pending" message rather than a working fix.
- **No auth.** The biggest hole. Mitigated by localhost-only
  binding in the MVP and by the deferred auth section in the
  scale-up notes below. Anyone with shell access to the host
  running the troubleshooter can impersonate an operator.
- **Audit log is a flat file, not append-only durable storage.**
  A misbehaving process or operator with file access can
  rewrite history. Acceptable for an MVP, real risk at scale.
- **Frontend has no error states beyond "something went wrong".**
  No retry, no offline mode, no optimistic UI. Functional but
  not polished.

## At Enterprise Scale

The MVP is one operator using the tool against a Fleet with five
test hosts. Production at 1,000+ devices changes every layer of
the design.

- **Auth is mandatory.** The tool is fronted by the same SSO
  the rest of the company uses, with role-based scoping that
  matches the support tier hierarchy. Tier-1 support sees only
  basic remediations; tier-2 sees more; engineering sees
  everything plus the ability to add new remediations to the
  registry. The audit log key changes from a placeholder string
  to the authenticated user's identity from the session JWT.

- **Audit log moves to Postgres** with a retention policy
  appropriate for the compliance regime in scope (90 days for
  SOC 2, longer for HIPAA, etc.). The audit log also ships to
  the SIEM in real time so security has visibility into who
  ran what against which device.

- **Remediation actions are gated by approval workflows for
  anything that touches more than one host.** A single-host fix
  is fine for tier-1 to fire. A bulk fix that touches more than
  20 hosts requires tier-2 sign-off. Anything across an entire
  team requires engineering approval. The approval routing
  lives in the registry so adding a new remediation
  automatically picks up the right gate.

- **Claude prompt template is versioned and eval-tested.** The
  prompt lives in a file under version control. Every change to
  the prompt runs through an eval suite that compares the new
  prompt's output against a labeled dataset of expected
  translations for the existing CIS policies. The static
  fallback dict becomes the labeled dataset for that eval.

- **Cost controls.** The Claude integration runs against an
  Anthropic team account with usage budgets per tier. Cache
  translations for repeated identical findings (same policy +
  same host OS = same translation, no need to re-call). Per-day
  rate limits per support user.

- **Deployment moves into the existing platform.** The
  Compose stack stops being a standalone unit and becomes part
  of the company's normal Kubernetes / ECS / Cloud Run
  rollout. The frontend ships through the same CDN as
  everything else, the backend runs as a normal service with
  health checks and metrics scraped by Prometheus.

- **Frontend gains the work the MVP defers.** Real error
  states, optimistic remediation UI, accessibility passes,
  internationalization if support is global, and a polished
  empty state for when a host has no failing policies. Plus
  the same RBAC visibility filters the backend enforces.

- **Remediation registry expands to cover the Apple MDM
  surface** once the HTTPS strategy from ADR-0003 is in place.
  FileVault enable/disable, Nudge prompts for OS updates,
  certificate profile pushes, profile removal flows. Each one
  ships with its own ADR documenting the API call shape and
  the failure modes.
