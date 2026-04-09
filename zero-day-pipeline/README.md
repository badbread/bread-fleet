# Zero-Day Response Pipeline

## The Problem

CISA publishes the Known Exploited Vulnerabilities (KEV) catalog — a list of CVEs that are actively being exploited in the wild. Fleet's built-in vulnerability scanner uses NVD data, which lags behind KEV by days or weeks. During that gap, your hosts are running software with known-exploited vulnerabilities and Fleet has no detection for them.

No automated bridge exists between KEV and Fleet. This module builds one.

## Architecture

```
CISA KEV JSON Feed
        |
        v
   kev_client          Fetch + cache the KEV catalog
        |
        v
     mapper             Registry lookup (curated) --> Claude fallback (reviewed)
        |
        v
   fleet_client         Deploy as Fleet policy via API
        |
        v
   Enrolled Hosts       2 demo hosts report pass/fail
        |
        v
   JSONL Audit Log      Every action recorded
```

**kev_client** fetches the CISA KEV JSON feed and caches it locally. The feed contains ~1,200 entries with CVE IDs, vendor/product names, descriptions, and due dates.

**mapper** takes a KEV entry and attempts to produce an osquery SQL query. It tries the curated product registry first. If no match is found, it falls back to Claude with structured prompting. Claude-generated queries include a confidence indicator and are never auto-deployed.

**fleet_client** takes a validated query and deploys it as a Fleet policy via the API. Supports dry-run mode for safe preview.

## Product Registry

The curated registry maps ~20 common Linux packages from KEV vendor/product pairs to osquery tables and package names:

- OpenSSL, curl, sudo, polkit, glibc
- Apache HTTP Server, nginx, Apache Tomcat
- Google Chrome, Mozilla Firefox
- Linux kernel, systemd, OpenSSH
- Samba, Exim, Dovecot, PostgreSQL, Redis

Each entry specifies the KEV vendor string, KEV product string, target osquery table (typically `deb_packages` or `rpm_packages`), and the package name to query for.

## Claude AI Assist

When a KEV entry doesn't match the curated registry, Claude acts as a fallback mapper. The prompt includes:

- The KEV entry (vendor, product, description, CVE ID)
- Available osquery tables relevant to package/software detection
- Example query patterns from the curated registry
- Instructions to return structured JSON with the SQL query and a confidence level

Claude returns a query with a confidence indicator (high/medium/low). **No Claude-generated query is ever auto-deployed.** The UI presents it for manual review, and the operator must explicitly approve before it reaches Fleet. This adds friction. That friction is correct — a wrong detection query is actively harmful, not merely unhelpful.

## Honest About Limitations

Roughly 15-20% of KEV entries can be mapped to osquery detection queries. The rest cannot, and the UI shows why:

- **Network appliances** (Cisco IOS, Palo Alto PAN-OS, Fortinet FortiOS) — osquery runs on endpoints, not on network gear.
- **SaaS products** (Salesforce, Microsoft 365, Atlassian Cloud) — no host-level artifact to query.
- **Mobile platforms** (iOS, Android) — osquery doesn't run on phones.
- **Windows-only software** — demo hosts run Linux.
- **Firmware/BIOS** — below osquery's observation layer.

This is shown transparently. Hiding the gap would be dishonest; explaining it demonstrates understanding of the problem space.

## What's In Scope

- Browsing the KEV feed with search and filtering
- Curated product registry mapping (~20 entries)
- Claude AI fallback with confidence scoring and manual approval
- Dry-run preview (see the query and what it would do, without deploying)
- Real Fleet deployment against 2 enrolled hosts
- Per-host pass/fail results for deployed policies
- JSONL audit log for every fetch, map, deploy, and delete action
- Stats endpoint showing coverage breakdown

## What's NOT In Scope

- Background polling (on-demand only for interactive demo)
- NVD version-range parsing (no CPE matching)
- GitOps PR workflow (direct API deployment only)
- Webhook alerting (no Slack/PagerDuty integration)
- Bulk deployment (one CVE at a time, deliberately)
- Windows or macOS detection queries

These are documented as the enterprise-scale path in [ADR-0008](../docs/adr/0008-zero-day-response-pipeline.md).

## Why This Matters

Every security team has this problem: a CVE hits the CISA KEV list, the SOC asks "are we affected?", and the answer takes hours of manual investigation. This module turns that into a 30-second workflow — fetch the KEV entry, generate a detection query, deploy it as a Fleet policy, and see which hosts are affected. For the ~20 products in the curated registry, it's fully automated. For everything else, Claude provides a starting point that a human reviews.

The interesting engineering isn't the API calls. It's the mapping problem — turning an unstructured vulnerability description into a correct osquery query — and being honest about where automation works and where it doesn't.

## Running Locally

```bash
# From the repo root
docker compose up
```

- **Frontend:** http://localhost:5175
- **Backend:** http://localhost:8090
- **Requires `.env`** with Fleet credentials (`FLEET_URL`, `FLEET_API_TOKEN`) and optionally `ANTHROPIC_API_KEY` for Claude fallback

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Health check |
| `GET` | `/api/kev/feed` | Fetch and return the KEV catalog (cached) |
| `GET` | `/api/kev/{cve_id}` | Get a single KEV entry by CVE ID |
| `POST` | `/api/kev/{cve_id}/map` | Map a KEV entry to an osquery query (registry + Claude fallback) |
| `POST` | `/api/kev/{cve_id}/deploy` | Deploy a mapped query as a Fleet policy (supports `dry_run` flag) |
| `GET` | `/api/policies` | List deployed zero-day policies |
| `GET` | `/api/policies/{id}/results` | Get per-host pass/fail results for a deployed policy |
| `DELETE` | `/api/policies/{id}` | Remove a deployed policy from Fleet |
| `GET` | `/api/stats` | Coverage stats: mapped, unmappable (with reasons), pending review |

## At Enterprise Scale

See [ADR-0008](../docs/adr/0008-zero-day-response-pipeline.md) for the full discussion. The short version: background poller replaces the button, GitOps PRs replace API calls, Claude suggestions get human approval gates, and webhooks notify the SOC when new KEV entries match installed software.
