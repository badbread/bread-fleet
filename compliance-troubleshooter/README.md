# Compliance Troubleshooter

A single-purpose tool that translates Fleet compliance findings into
plain English for support staff, with one-click remediation paths
where automation is safe and an audit trail for everything else.

## What it solves

When a device fails a CIS policy in Fleet, the policy result a
support person sees looks like this:

> Host failed `CIS 4.1.1.1 auditd package installed`. Query
> returned 0 rows from `deb_packages`. Status: failing.

That sentence is meaningless to a support person who doesn't read
SQL or know what auditd is. They escalate to engineering, the
ticket sits in a queue, eventually an engineer types
`apt-get install auditd` and closes it. The escalation costs more
than the fix.

This tool puts a translation layer between Fleet and support so
the same finding looks like this:

> The audit logging package is missing on Bob's laptop. Without it,
> the device can't keep a tamper-resistant log of administrative
> actions, which is a compliance blocker for SOC 2.
>
> Fix: Click "Install audit logging" below. The change takes
> about 30 seconds and does not require a reboot.
>
> [Install audit logging] [Re-check after fix]

Same finding. Different audience. The technical content is in the
backend; the UI is in the support person's language.

## Architecture

```
+--------------+        +------------------+        +----------+
|              |        |                  |        |          |
|  Support     | ---->  |  Troubleshooter  | ---->  |  Fleet   |
|  browser     |        |  backend         |        |  REST    |
|  (React)     | <----  |  (FastAPI)       | <----  |  API     |
|              |        |                  |        |          |
+--------------+        +--------+---------+        +----------+
                                 |
                        +--------v---------+        +----------+
                        |                  |        |          |
                        |  Claude API      | <----  |  prompt  |
                        |  (translation    |        |  template|
                        |  layer)          |        |          |
                        +--------+---------+        +----------+
                                 |
                        +--------v---------+
                        |  JSONL audit log |
                        |  (every search,  |
                        |  every fix)      |
                        +------------------+
```

The backend has four responsibilities:

1. **Proxy and enrich Fleet data.** Calls Fleet's REST API for
   host search and policy results, then enriches each failing
   policy with a plain-English translation.
2. **Translate.** Sends the policy metadata + the host context to
   Claude with a structured-output prompt that returns JSON the
   frontend can render directly. A static fallback dict covers the
   12 known CIS policies so the MVP runs without an API key.
3. **Remediate.** A per-policy remediation registry maps each
   fixable finding to a Fleet script-execution call. The
   `auditd_install` remediation runs end to end against the live
   Fleet. Everything else returns "not yet implemented" with the
   recommended manual steps.
4. **Audit.** Every search, every translation request, every
   remediation attempt, every re-check is appended to a JSONL log
   with timestamp, operator (placeholder until auth lands),
   target host, action, outcome.

## What's in scope for the MVP

- Search for a host by hostname
- Display compliance summary (pass/fail count)
- Translate every failing policy via Claude (or static fallback)
- One working end-to-end remediation: install auditd via Fleet's
  script execution API
- Re-check button that re-fetches policy state after a fix
- JSONL audit log
- Compose stack that runs alongside the existing fleet-server

## What's explicitly NOT in scope for the MVP

- Authentication / RBAC (single-operator, localhost-only)
- Multi-host bulk remediation
- Apple MDM remediations (FileVault, profile push, Nudge) because
  the Fleet deployment is currently HTTPS-blocked for MDM, see
  ADR-0003
- Real-time WebSocket updates (re-check is operator-driven)
- Postgres-backed audit log
- Production error handling (current MVP fails fast with clear
  errors, does not retry)
- A polished onboarding flow (operator points it at a Fleet URL
  and a token, that is the entire setup)

These are tracked in the ADR for the Troubleshooter (ADR-0005)
under the "At Enterprise Scale" section, which is what they would
look like in a production deployment.

## Why this matters

Three things this tool demonstrates that a vanilla Fleet
deployment does not:

1. **A bridge between engineering and support that reduces
   ticket volume.** Most CPE shops have a Slack channel called
   something like `#endpoint-help` where support escalates to
   engineering. This tool moves the simpler tickets into
   self-service.
2. **An LLM used for the right job.** The translation layer is
   the kind of fuzzy structured-to-natural-language problem
   LLMs are genuinely good at, and the static-fallback pattern
   means the tool is not held hostage by API availability.
3. **An audit trail by default.** Every action by support is
   logged before it runs. This is the difference between a tool
   that scales and a tool that becomes a liability the first
   time someone runs the wrong remediation.

## Running it locally

The tool runs as its own Compose stack. It expects to talk to a
running Fleet instance and (optionally) Claude. The exact runtime
configuration lives in `.env` (gitignored); `.env.example` shows
the required variables.

```
docker compose up -d
```

Frontend listens on `http://localhost:5173`. Backend listens on
`http://localhost:8088`. Both have liveness endpoints.

If `ANTHROPIC_API_KEY` is set, the backend uses Claude for
translations. If not, it falls back to a static dict covering the
12 CIS policies in `gitops/default.yml`. Either mode works for the
demo.

## At enterprise scale

ADR-0005 covers the deltas in detail. The summary:

- Auth becomes mandatory and tied to the existing SSO. The audit
  log key changes from "operator placeholder" to "real human user
  with a session JWT."
- The audit log moves to Postgres with a retention policy and
  ships to the SIEM in real time.
- Remediation actions are gated by an approval workflow for
  anything that touches more than one host.
- The Claude prompt template moves to a versioned file with eval
  coverage so a model swap or a prompt change is reviewed.
- The static fallback dict becomes a tested dataset that Claude
  output is compared against in CI to catch translation drift.
- Frontend gains real auth, error states, optimistic UI for
  remediations, and accessibility passes.
