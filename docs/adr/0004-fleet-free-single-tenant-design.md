# ADR-0004: Single-tenant GitOps shape on Fleet Free

## Status

Accepted

## Context

The original GitOps design had three teams from day one:
`linux-servers` for infrastructure VMs, `linux-workstations` for
developer Linux laptops, and `macos-corporate` for Apple endpoints.
Each team would have its own enrollment secret, agent options, and
policy scope. This is the right shape for any real CPE deployment
because it gives you separate rollout cadences per device class,
distinct policy bars per team, and clean enrollment surfaces that
don't accidentally apply server-grade settings to a developer
laptop.

The team YAMLs were authored, the dry-run was clean, and then
`fleetctl gitops --dry-run` returned:

```
[!] skipping team config teams/linux-servers.yml since teams are only
    supported for premium Fleet users
[!] skipping team config teams/linux-workstations.yml since teams are
    only supported for premium Fleet users
[!] skipping team config teams/macos-corporate.yml since teams are
    only supported for premium Fleet users
```

Multi-team is gated behind Fleet Premium. Fleet Free supports
exactly one logical bucket: the global "no team" group that all
hosts enroll into by default. There is no upgrade path inside Fleet
Free that gets you teams.

## Decision

Collapse the GitOps tree to a single global configuration file at
`gitops/default.yml`. All policies, queries, agent options, and the
enrollment secret live at the global level. Every enrolled host
lands in the global pool and receives the same policy surface.

Preserve the originally-authored team YAMLs as **documentation,
not configuration**. They move from `gitops/teams/` to
`gitops/reference-teams/` with a README explaining that they are
not applied and describing what they would do on a Premium
deployment.

`apply.sh` only passes `default.yml` to `fleetctl gitops`. The
reference-teams directory is never touched at apply time. Operator
intent is unambiguous: nothing in `reference-teams/` is live.

## Alternatives Considered

1. **Pay for Fleet Premium.** The right answer for any real
   production deployment. Not available here because the project
   uses Fleet Free, but documented as the recommended path at
   scale.

2. **Run three separate Fleet Free instances**, one per logical
   team. Each instance would have its own MySQL, Redis, Compose
   stack, and runtime directory. Technically possible. Rejected
   because it triples every operational burden (backups, upgrades,
   credentials, deploy pipelines) for a benefit that Fleet Premium
   gives you for the cost of a license. The single-host design
   from ADR-0001 is non-negotiable for this deployment.

3. **Use Fleet's host labels as a tenancy substitute.** Fleet Free
   supports labels, which can scope queries and policies at query
   time. Useful for filtering, but labels do not carry agent
   options, do not have their own enrollment secrets, and do not
   represent a tenancy boundary. Pretending labels are teams
   creates ambiguity about what's actually scoped versus what's
   global.

4. **Abandon GitOps and manage Fleet through the web UI.** Removes
   the Free vs Premium distinction entirely (the web UI works on
   both tiers). Rejected because it loses the audit trail, the
   reproducibility, and the entire reason for using GitOps in the
   first place.

## Tradeoffs

- **No team-scoped rollouts.** A new policy goes live for every
  host on the next config refresh. There is no canary group, no
  staged deployment, no "soak this on the linux-servers team for
  two weeks before promoting it to all hosts."
- **No per-team agent options.** If linux servers want a 10-second
  distributed_interval and macOS laptops want a 60-second interval
  to spare battery, Fleet Free cannot express that distinction.
  Global settings apply to every host.
- **Coarser enrollment surface.** Every host uses the same
  enrollment secret. Rotating it requires rotating across the
  whole fleet at once.
- **The reference-teams directory could drift from default.yml.**
  When `default.yml` gains a new policy, the reference team YAMLs
  should also be updated to keep the "what would Premium look
  like" story accurate. There is no automated check for this drift
  today; it is a documented manual responsibility.

## At Enterprise Scale

This entire ADR exists because of a tier limitation. At enterprise
scale, where Fleet Premium is in scope, the design looks like the
original three-team plan, with several additions:

- **Team boundaries match operational reality.** Teams are scoped
  by who owns the device and who owns the on-call for that device
  class. `linux-servers` is owned by infra; `corporate-macos` is
  owned by IT; `field-ios` is owned by IT but has different
  rollout cadences than the macOS laptops because iOS users have
  less tolerance for prompts.
- **Per-team enrollment secrets are rotated independently.** Each
  team's secret has its own rotation schedule and revocation
  procedure. A leak in one team's secret does not require the
  whole fleet to re-enroll.
- **Agent options diverge.** Servers run aggressive distributed
  intervals because they're plugged in. Laptops run slow intervals
  because of battery and bandwidth. ES (EndpointSecurity) on
  macOS is enabled per-team, never globally, because it has real
  CPU cost.
- **Policy rollouts are staged through teams.** A new CIS control
  lands first on `policy-canary` (a small team of opt-in volunteer
  hosts), soaks for a week, promotes to `linux-servers` for two
  weeks, and finally promotes to all teams. Each promotion is a PR
  to the GitOps repo with a reviewer.
- **The reference-teams pattern in this repo becomes the actual
  team set.** Move the YAMLs out of `reference-teams/` back to
  `teams/`, update `apply.sh` to include them, and turn off the
  "skipping team config" warning by upgrading the license. Ten
  minutes of work, plus the cost of Premium.
