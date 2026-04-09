# osquery patterns and packs

Custom osquery query packs are defined inline in
`gitops/default.yml`, not in this directory. This README captures
the patterns and assumptions the queries follow, plus a couple of
ideas worth raising at the team level.

## Where the queries actually live

`gitops/default.yml` under the `queries:` key. 13 queries organized
into four buckets:

| Bucket | Queries | Purpose |
|---|---|---|
| System telemetry | system_info, os_version, uptime, disk_free, installed_packages_linux | Inventory and baseline |
| Security posture | listening_tcp_ports, users_with_uid_zero, suid_binaries, sshd_config_file_integrity, crontab_entries | Audit surface |
| Compliance signals | firewall_modules_loaded, time_sync_processes | Feeds the CIS policy set in the same file |
| Incident response | new_processes | Differential, observer-runnable for live investigation |

The grouping is conceptual; in the YAML they are a flat list. Each
query has its rationale documented inline.

## Patterns this repo follows

- **Filter in SQL, not in the result handler.** A query that returns
  10k rows and post-filters is a query that wrecks hosts with slow
  disks. `listening_tcp_ports` joins against `processes` in-query so
  the result set is already enriched and already trimmed.

- **Snapshot vs differential is a deliberate choice per query.** State
  queries (`os_version`, `users_with_uid_zero`) ship as `snapshot`.
  Event queries (`new_processes`) ship as
  `differential_ignore_removals` so Fleet only logs creation events
  and not exits, halving the log volume. Mixing them up means
  shipping data nobody asked for or missing data nobody can recover.

- **Intervals match how often the underlying data actually changes.**
  Kernel module list at 60 seconds is wasteful (modules don't change
  in normal operation). Process events at 3600 seconds is useless
  (everything will have rotated by then). The intervals in the pack
  are picked per-query, not picked once and applied to everything.

- **Observer runnable on the safe ones.** Anything that doesn't
  expose secrets and isn't expensive gets `observer_can_run: true`
  so a SOC analyst can trigger a live query without escalating
  privileges.

- **No `SELECT *`.** osquery silently adds columns when tables
  evolve, and `SELECT *` queries break in surprising ways on the
  next image bump. Every query names the columns it actually wants.

## Assumptions baked into the queries

- **Linux + macOS, not Windows.** A few queries are
  `platform: darwin,linux,windows` because the underlying tables
  exist everywhere (`system_info`, `os_version`, `uptime`). The
  rest are `platform: darwin,linux` or `linux` only because the
  tables they hit are POSIX-specific. Windows queries would be
  their own pack with their own patterns.

- **Ubuntu's default file ownership for `/var/log/syslog`.** The
  `sshd_config_file_integrity` query and the CIS 4.2.3 policy
  both deal with the same trap: Ubuntu Server installs the file
  owned by `syslog:adm` mode 0640, not `root:root`. The default
  is CIS-compliant, but a naive policy that requires `uid = 0`
  rejects it. Documented in detail in ADR-0002 and in the policy
  itself.

- **`shadow` table requires root context.** osquery has to run as
  root (which orbit handles) for the shadow table to return rows.
  None of the current queries hit shadow but a future policy
  about password aging would need to.

## Ideas worth raising at the team level

1. **Per-query performance budgets.** Fleet exposes `system_time`,
   `user_time`, and `memory` for each query in its admin API. A
   small CI check could parse those numbers per host class and
   reject any PR adding a query that exceeds a per-team budget on
   a reference host. Prevents the "one expensive query tanks
   everyone's battery" failure mode that hits CPE teams quarterly.

2. **`process_events` vs ES tradeoffs on macOS.** On macOS the
   `process_events` table requires EndpointSecurity, which has
   real CPU cost and real entitlement requirements. Worth knowing
   whether a team runs it continuously or only triggers it on
   demand via live queries. The answer changes the agent options
   significantly and the choice should be explicit, not default.
