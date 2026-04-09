# ADR-0008: Zero-Day Response Pipeline

## Status

Accepted

## Context

Fleet's built-in vulnerability scanner uses NVD data to detect known vulnerabilities on enrolled hosts. CISA's Known Exploited Vulnerabilities (KEV) catalog tracks actively exploited vulnerabilities, often days or weeks before NVD publishes advisories or before Fleet's scanner picks them up. No automated bridge exists between the KEV catalog and Fleet's detection capabilities.

The KEV catalog has roughly 1,200 entries, but only a fraction map cleanly to osquery detection queries. Many KEV entries target network appliances, SaaS platforms, or mobile products that osquery simply cannot see — it runs on endpoints, not on Palo Alto firewalls or Salesforce tenants. The CVE-to-osquery mapping challenge is the core technical problem this module addresses.

## Decision

Build a module that:

1. **Fetches the CISA KEV JSON feed** and caches it locally.
2. **Maps KEV entries to osquery SQL** via a curated product registry (~20 entries for common Linux packages like OpenSSL, curl, sudo, Apache, nginx, Chrome).
3. **Uses Claude API as a fallback** for unknown products. Claude receives the KEV entry details, available osquery tables, and example query patterns. It returns SQL with a confidence indicator. Claude-generated queries are never auto-deployed — they require manual approval before reaching Fleet.
4. **Deploys generated queries as Fleet policies** via the Fleet API, targeting the 2 enrolled demo hosts.
5. **Runs on-demand** (not as a background poller) so the demo is interactive — the interviewer triggers a scan, sees results, and watches a policy appear in Fleet in real time.
6. **Includes a dry-run toggle** for safe preview of what would be deployed without touching Fleet.
7. **Writes a JSONL audit log** for every action taken.

## Alternatives Considered

### 1. Claude-only SQL generation

Use Claude to generate osquery SQL for every KEV entry, no curated registry. This is impressive but unreliable for SQL that must be correct. A wrong detection query is actively harmful — it produces false positives (or worse, false negatives) with no signal that anything is wrong. This is fundamentally different from the compliance troubleshooter, where a bad natural-language-to-SQL translation is merely unhelpful. Here, a bad query silently enters the detection pipeline.

**Rejected** as the primary path. Added as a reviewed fallback with confidence scoring and mandatory manual approval.

### 2. Full NVD integration for version ranges

Pull structured CPE data from NVD to get exact affected version ranges, then generate precise version-comparison queries. This is the correct long-term approach but massively out of scope. The NVD API has rate limits, version string parsing requires CPE matching logic, and the fundamental mapping problem (which osquery table? which package name?) remains identical.

**Deferred.**

### 3. GitOps-only deployment (generate YAML PRs, not API calls)

Generate Fleet policy YAML and open PRs against a GitOps repo instead of calling the Fleet API directly. More realistic for production workflows but less demonstrable in a live demo — the interviewer cannot see a policy appear in Fleet in real time.

**Rejected** for the demo. Documented as the at-scale deployment path.

### 4. Background poller only

Run the KEV check on a timer and present results after the fact. This is the "I started it 20 minutes ago, trust me" problem — it removes the interactive element that makes the demo compelling.

**Rejected** for the demo. Trivially added as an asyncio task in the FastAPI lifespan for production use.

## Tradeoffs

- **Coverage is honest but limited.** The curated registry covers ~20 products out of ~1,200 KEV entries (~15-20%). The remaining entries are network appliances, SaaS products, mobile platforms, and other things osquery cannot observe. The UI shows this transparently with reasons for unmappable entries rather than hiding the gap.
- **Version comparison is simplified.** Queries check for package presence and installed version, but do not perform full version-range comparison against NVD CPE data. A package showing up as "installed" is flagged; precise "affected versions 2.1.0 through 2.1.4" logic is not implemented.
- **API deployment bypasses GitOps review.** Policies are pushed directly via Fleet API, skipping any change-review workflow. Acceptable for a 2-host demo environment; at scale this becomes a PR to a GitOps repo with human approval.
- **Claude-assisted mappings add friction.** Requiring manual approval for AI-generated queries slows the response pipeline but prevents bad SQL from reaching Fleet. This is the right tradeoff — speed matters less than correctness in detection.

## At Enterprise Scale

- Background poller on a 6-hour cron replaces the on-demand button.
- Claude API serves as a "suggest mapping" assistant; human approval is required before any AI-generated query is deployed.
- Generated policies become pull requests to a GitOps repo, gated behind code review.
- Webhook integration to Slack/PagerDuty when a new KEV entry matches installed software on enrolled hosts.
- Full CPE version-range parsing via NVD structured data for precise affected-version detection.
- Coverage metrics tracked over time (mapped vs. unmappable, reasons for gaps).
- The product registry becomes a versioned config or database with its own review workflow for adding new entries.
