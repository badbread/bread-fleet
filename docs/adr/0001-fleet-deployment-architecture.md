# ADR-0001: Fleet deployment architecture

## Status

Accepted (partially superseded by ADR-0002 on data storage and ADR-0003 on ingress)

## Context

A single-host Fleet deployment is the right shape for the kind of
work this repo demonstrates: it's reproducible, fits on a Docker
host, exercises every part of Fleet's operational surface (server,
MySQL, Redis, schema migrations, agent enrollment, GitOps), and
keeps the architecture small enough to discuss end-to-end.

The decision space included how to package the stack, where state
lives, how the host gets bootstrapped, and how config changes flow
to Fleet's API.

## Decision

Fleet, MySQL 8.0, Redis 7, and an optional `cloudflared` sidecar are
defined in a single `docker-compose.yml` under `fleet-server/`.
Schema migrations run as a one-shot `fleet-init` service that uses
`depends_on: condition: service_completed_successfully` to gate the
main Fleet container, so version upgrades surface migration failures
loudly instead of silently.

The compose file lives in this repo as the canonical source. At
deploy time, the file is copied to a runtime directory on the
Docker host and `docker compose up -d` runs from there. A separate
runtime `.env` (gitignored) holds real secrets and is referenced by
the compose file via standard variable substitution.

GitOps configuration (org settings, agent options, queries,
policies, enrollment secrets) lives alongside the compose stack in
`gitops/` and is applied via `fleetctl gitops` from `apply.sh`.

## Alternatives Considered

1. **Multiple Fleet instances per device class.** Run `linux-fleet`,
   `macos-fleet`, etc. as separate Compose stacks. Rejected because
   it triples the operational surface (three MySQL backups, three
   sets of credentials, three apply pipelines) for a benefit that
   Fleet Premium's multi-team feature already gives you for free at
   the right tier. Documented further in ADR-0004.

2. **Kubernetes deployment.** Helm chart, StatefulSet for MySQL,
   Service mesh, etc. Rejected because it adds an operational layer
   that has nothing to do with what the repo is trying to
   demonstrate. The Fleet team's own quickstart is Docker Compose;
   matching that lets the work focus on Fleet's surface, not on
   k8s plumbing.

3. **Native systemd units.** Install Fleet, MySQL, and Redis directly
   on the host as system services. Rejected because it splits the
   stack across two management planes (apt + systemd vs Compose),
   makes the host non-disposable, and requires a separate strategy
   for version upgrades.

4. **Inline migrations in the main Fleet container.** Let the Fleet
   server's startup logic call `fleet prepare db` itself. Rejected
   because migration failures would surface as a crash-looping main
   container, mixing schema problems with actual runtime errors and
   making debugging harder.

## Tradeoffs

- **Single point of failure.** One Fleet, one MySQL, one Redis,
  one host. Acceptable for a single-tenant deployment, not for
  production at scale.
- **Manual host upgrades.** OS patches and Docker version bumps on
  the host happen out-of-band. There's no rolling upgrade pattern.
- **NAS dependency for the compose file location.** If the NAS share
  is unavailable, the host can still run the existing containers
  (they're already running) but it can't apply config changes until
  the share comes back. Mitigated because the runtime `.env` and
  named volumes are local.
- **Compose `profiles` for `cloudflared` is opt-in.** Default
  `docker compose up -d` does not start the tunnel sidecar. This is
  deliberate (see ADR-0003) but means anyone who wants tunnel
  ingress has to know about the `--profile tunnel` flag.

## At Enterprise Scale

This shape does not generalize past one host. A real deployment with
1,000+ devices would change every layer:

- **HA Fleet.** Two or more Fleet servers behind a load balancer,
  active-active. Sticky sessions are unnecessary because Fleet is
  largely stateless above the database.
- **Externalized MySQL.** Managed RDS or equivalent with multi-AZ
  failover, automated backups, point-in-time recovery, and a read
  replica for analytics. Local Docker volumes are not an option.
- **Externalized Redis.** Managed cache (Elasticache, MemoryDB)
  with cluster mode for the live-query pub/sub workload. Fleet
  treats Redis as ephemeral so failover is forgiving.
- **Schema migrations as a CI job.** The one-shot
  `fleet-init` pattern stays, but it runs in a CI pipeline before
  the main Fleet rollout, with explicit migration approval gates
  for major version bumps.
- **GitOps apply via CI service account.** No more workstation-run
  `apply.sh`. Every PR merge triggers a `fleetctl gitops` call from
  CI with an API-only service account (Premium feature). PRs that
  fail dry-run get blocked at review.
- **Compose stack -> orchestration stack.** Either Kubernetes with
  the Fleet Helm chart or ECS/Cloud Run depending on the cloud
  posture. The single-host Compose pattern is fine for proving the
  shape but does not survive contact with production load.
