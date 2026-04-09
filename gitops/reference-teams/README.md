# reference-teams/

> **These files are NOT applied.** They are documentation of what a
> Fleet Premium multi-team configuration would look like for this
> deployment. See [ADR-0004](../../docs/adr/0004-fleet-free-single-tenant-design.md)
> for the full reasoning.

## Why these exist

Fleet's multi-team feature (teams, per-team agent options, per-team
enrollment secrets, policy scoping) is a Premium-only feature. This
deployment runs Fleet Free, which supports exactly one logical
bucket (the global "no team" group).

The GitOps tree in this repo therefore applies only `../default.yml`,
which configures the single global surface. But the multi-team design
is still the right shape for a real CPE team, and I wanted to
demonstrate that I understand it. So the team YAMLs live here as
reference material.

## The reference teams

| File | Purpose |
|---|---|
| [`linux-servers.yml`](linux-servers.yml) | Infrastructure VMs and long-running servers. Tighter check-in intervals, shorter host expiry (14 days), stricter CIS posture. |
| [`linux-workstations.yml`](linux-workstations.yml) | Developer Linux laptops and desktops. Slower check-in (60s) for battery, longer host expiry (60 days) for travel. |
| [`macos-corporate.yml`](macos-corporate.yml) | macOS endpoints including the OpenCore test VM. Would be enrolled once an HTTPS strategy for MDM is decided. See ADR-0003. |

## How they would be applied on Fleet Premium

On a Premium install, `apply.sh` would be extended to pass each file
to `fleetctl gitops` as a `-f` argument:

```bash
fleetctl gitops --context fleet \
  -f default.yml \
  -f reference-teams/linux-servers.yml \
  -f reference-teams/linux-workstations.yml \
  -f reference-teams/macos-corporate.yml
```

Each team would be created as a first-class object in Fleet with its
own enrollment secret, agent options, and (eventually) scoped
policies and queries. Hosts enrolling with a team's secret would be
auto-assigned to that team.

## Keeping them in sync with default.yml

When `default.yml` is updated with new policies, queries, or agent
options, the reference team files should be updated to match if they
would also have applied. This keeps the documentation accurate for
the "what would Premium look like" story, and makes the eventual
migration to Premium (if it ever happens) a simple directory move
rather than a rewrite.

## Can I just apply them anyway?

No. `fleetctl gitops` will emit a skip warning and move on:

```
[!] skipping team config reference-teams/linux-servers.yml
    since teams are only supported for premium Fleet users
```

The file is parsed, schema-validated, and then ignored. The apply.sh
script omits them from its command line entirely to avoid the warning.
