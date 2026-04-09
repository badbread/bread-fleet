# GitOps for Fleet

The substrate every CPE team running Fleet needs: configuration
defined as YAML, applied through `fleetctl gitops`, with secrets
referenced symbolically and provided at apply time from a
gitignored runtime `.env`. This directory holds the version
controlled side; the runtime side lives only on the Docker host.

## Layout

```
gitops/
├── README.md                 <- this file
├── default.yml               <- the only file applied to Fleet
├── apply.sh                  <- workstation-run deploy helper
└── reference-teams/          <- multi-team design (not applied, see ADR-0004)
    ├── README.md
    ├── linux-servers.yml
    ├── linux-workstations.yml
    └── macos-corporate.yml
```

`default.yml` is the canonical source for everything Fleet exposes
through GitOps: org settings, agent options, queries, policies,
the global enrollment secret. The reference-teams subdirectory is
not part of the apply flow. ADR-0004 explains why and what it
exists for.

## What this directory exists to demonstrate

Three things, in order of how interesting they are to a reader:

1. **Schema-validated apply with templated secrets.** `apply.sh`
   does the source-vs-runtime split: scp the YAML to a staging
   directory on the Docker host, source the runtime `.env`, run
   `fleetctl gitops` with env var substitution. Secrets never
   live in the repo, never live in the staging directory beyond
   the duration of the apply, and never appear in any CI artifact.
   The pattern works the same way against a CI service account
   when you have one.

2. **Conditional policy SQL.** The CIS 4.2.3 policy in `default.yml`
   is the example worth reading. The naive query (which the
   original version of this repo used) checks `/var/log/syslog`
   permissions and fails on every Ubuntu Server install that uses
   journald-only logging. The current version uses
   `NOT EXISTS (SELECT 1 FROM deb_packages WHERE name = 'rsyslog')`
   to short-circuit on hosts where rsyslog isn't installed at all,
   and a subquery against the `users` table to resolve the syslog
   user's UID at query time so the policy accepts both root and
   syslog ownership. Two patterns most CIS-policy starter kits
   miss.

3. **The reference-teams handoff.** When this deployment graduates
   to Fleet Premium, the team YAMLs in `reference-teams/` are the
   shape that lights up. Moving them is one directory rename and
   a one-line edit to `apply.sh`. The "Premium upgrade path" is
   real, not aspirational.

## Running apply.sh

```bash
export FLEET_DEPLOY_SSH=your-docker-host-ssh-alias
export FLEET_RUNTIME_DIR=/opt/fleet     # default
export FLEETCTL_CONTEXT=fleet           # default

./gitops/apply.sh --dry-run             # validate, change nothing
./gitops/apply.sh                       # apply for real
```

The runtime `.env` on the Docker host must define every variable
that `default.yml` references via `$VAR`. `apply.sh` checks for
the required keys before invoking `fleetctl` and fails loudly if
any are missing, rather than letting Fleet apply a half-substituted
YAML.

## Required runtime .env keys

| Variable | Where it's used |
|---|---|
| `FLEET_SERVER_URL` | Baked into agent enrollment packages and invite emails |
| `FLEET_ORG_NAME` | Display name in the Fleet UI |
| `GLOBAL_ENROLL_SECRET` | The single enrollment secret for the global team |
| `LINUX_SERVERS_ENROLL_SECRET` | Required by reference-teams (not applied) |
| `LINUX_WORKSTATIONS_ENROLL_SECRET` | Same |
| `MACOS_CORPORATE_ENROLL_SECRET` | Same |

The reference-team secrets are checked even though their YAMLs are
not applied, so that a future Premium upgrade does not require
adding new env vars on top of the existing deployment.

## Secrets handling

No secrets in this directory, ever. The YAML references env vars
symbolically. The real values live in the runtime `.env` on the
Docker host, mode `0600`, gitignored. Pre-commit gitleaks scans
catch any drift; CI runs `gitleaks git` over the full history on
every push.
