# Architectural Decision Records

Every non-trivial decision in this repo gets an ADR. Numbered,
dated, immutable once accepted. When a decision is revisited a
new ADR is written that supersedes the old one; the original
stays in the tree so the reasoning history is preserved.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-fleet-deployment-architecture.md) | Fleet deployment architecture (Docker Compose, single host, NAS-backed config, one-shot migration service) | Accepted (partially superseded by 0002 and 0003) |
| [0002](0002-mysql-redis-on-local-volumes.md) | MySQL and Redis on local Docker volumes, not NFS bind mounts (NFS root_squash vs container chown) | Accepted |
| [0003](0003-lan-only-ingress.md) | LAN-only ingress, with documented at-scale path-restricted Cloudflare Tunnel design | Accepted |
| [0004](0004-fleet-free-single-tenant-design.md) | Single-tenant GitOps shape on Fleet Free, reference-teams as Premium-design documentation | Accepted |
| [0005](0005-compliance-troubleshooter-design.md) | Compliance Troubleshooter design (FastAPI + React + Claude API translation, JSONL audit, per-policy remediation registry) | Accepted |

## Format

Every ADR follows the same structure:

- **Status**: Accepted, Proposed, or Superseded by ADR-XXXX
- **Context**: what problem or question prompted this decision
- **Decision**: what was decided and why
- **Alternatives Considered**: what else was evaluated and why each was rejected
- **Tradeoffs**: what is being given up
- **At Enterprise Scale**: how the decision changes with 1,000+ devices, a team of engineers, and production SLAs
