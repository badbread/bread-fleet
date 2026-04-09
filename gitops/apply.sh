#!/usr/bin/env bash
# ============================================================================
# gitops/apply.sh
#
# Deploy the GitOps YAML in this directory to the running Fleet server.
#
# This script is meant to be run from a workstation that has:
#   1. A copy of this repo (so it can read the YAML files)
#   2. SSH access to the Docker host running Fleet
#
# It handles everything else: copying the YAML to the Docker host,
# sourcing the runtime .env (which contains enrollment secrets and the
# FLEET_SERVER_URL the YAML references), and invoking `fleetctl gitops`
# with the right -f flags.
#
# Usage:
#   ./apply.sh                    # real apply (changes Fleet state)
#   ./apply.sh --dry-run          # validate YAML without changing anything
#
# Required env vars (the apply.sh wrapper checks them):
#   FLEET_DEPLOY_SSH              SSH destination for the Docker host,
#                                 e.g. "user@host" or an SSH config
#                                 alias.
#
# Optional env vars:
#   FLEET_RUNTIME_DIR             Path on the Docker host where Fleet's
#                                 runtime .env lives. Default: /opt/fleet
#   FLEETCTL_CONTEXT              fleetctl context name. Default: fleet
#
# Why this design:
#   The YAML is the source of truth, committed in git. The runtime .env
#   holds secrets and is not committed. This script ties them together
#   at apply time without either touching the other's storage.
# ============================================================================

set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="--dry-run"
  echo "[apply.sh] DRY RUN mode, no changes will be made"
fi

: "${FLEET_DEPLOY_SSH:?Set FLEET_DEPLOY_SSH to the Docker host SSH destination (e.g. user@host)}"
FLEET_RUNTIME_DIR="${FLEET_RUNTIME_DIR:-/opt/fleet}"
FLEETCTL_CONTEXT="${FLEETCTL_CONTEXT:-fleet}"

# Resolve the gitops/ directory (the one this script lives in) so the
# script works whether invoked from the repo root or from inside gitops/.
GITOPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[apply.sh] gitops source: $GITOPS_DIR"
echo "[apply.sh] target host:   $FLEET_DEPLOY_SSH"
echo "[apply.sh] runtime dir:   $FLEET_RUNTIME_DIR"
echo "[apply.sh] fleet context: $FLEETCTL_CONTEXT"

# Stage the YAML files on the Docker host in a temp directory. We use
# a timestamped directory so concurrent runs don't clobber each other
# and we can inspect the last apply's input if something goes wrong.
#
# NOTE: reference-teams/ is intentionally not copied. Fleet Free is
# single-tenant and cannot apply multi-team configurations (that is a
# Premium feature). The team YAMLs in reference-teams/ exist as
# documentation of what a Premium deployment would look like.
# See docs/adr/0004-fleet-free-single-tenant.md.
STAGE_DIR="/tmp/fleet-gitops-$(date +%Y%m%d-%H%M%S)"
echo "[apply.sh] staging to $FLEET_DEPLOY_SSH:$STAGE_DIR"

# shellcheck disable=SC2029
ssh "$FLEET_DEPLOY_SSH" "mkdir -p $STAGE_DIR"
scp -q "$GITOPS_DIR/default.yml" "$FLEET_DEPLOY_SSH:$STAGE_DIR/default.yml"

# Run fleetctl gitops on the Docker host. The `-f` flag is repeated
# once per file. Env vars referenced in the YAML ($FLEET_SERVER_URL,
# $GLOBAL_ENROLL_SECRET, $LINUX_SERVERS_ENROLL_SECRET, etc.) are
# sourced from the runtime .env before the fleetctl call, so they are
# available to fleetctl's env substitution.
# shellcheck disable=SC2029
ssh "$FLEET_DEPLOY_SSH" bash -s -- "$STAGE_DIR" "$FLEET_RUNTIME_DIR" "$FLEETCTL_CONTEXT" "${DRY_RUN:-}" <<'REMOTE'
set -euo pipefail
STAGE_DIR="$1"
RUNTIME_DIR="$2"
CONTEXT="$3"
DRY_RUN="${4:-}"

if [[ ! -f "$RUNTIME_DIR/.env" ]]; then
  echo "[apply.sh:remote] ERROR: $RUNTIME_DIR/.env not found on the Docker host." >&2
  echo "[apply.sh:remote] This file must contain FLEET_SERVER_URL, FLEET_ORG_NAME," >&2
  echo "[apply.sh:remote] GLOBAL_ENROLL_SECRET, and per-team enrollment secrets." >&2
  exit 2
fi

# Source the runtime env. The `set -a` + source + `set +a` idiom
# exports every variable defined in .env into the current shell env
# so they are visible to the fleetctl subprocess.
set -a
# shellcheck disable=SC1090
source "$RUNTIME_DIR/.env"
set +a

# Sanity-check the required vars are present. Fail loudly if anything
# is missing, rather than letting fleetctl apply a half-substituted YAML.
for var in FLEET_SERVER_URL FLEET_ORG_NAME GLOBAL_ENROLL_SECRET \
           LINUX_SERVERS_ENROLL_SECRET LINUX_WORKSTATIONS_ENROLL_SECRET \
           MACOS_CORPORATE_ENROLL_SECRET; do
  if [[ -z "${!var:-}" ]]; then
    echo "[apply.sh:remote] ERROR: $var is not set in $RUNTIME_DIR/.env" >&2
    exit 3
  fi
done

cd "$STAGE_DIR"
# Build the command array so an empty DRY_RUN doesn't pass an empty
# string as a flag to fleetctl (which would cause "unknown flag").
CMD=(fleetctl gitops --context "$CONTEXT" -f default.yml)
if [[ -n "$DRY_RUN" ]]; then
  CMD+=("$DRY_RUN")
fi
echo "[apply.sh:remote] running: ${CMD[*]}"
"${CMD[@]}"
REMOTE

echo "[apply.sh] done"
