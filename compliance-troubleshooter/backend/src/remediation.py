"""Remediation registry.

Each entry in the registry maps a remediation_id (string) to either:

  - An automated handler that runs a shell script via Fleet's script
    execution API and returns the result.
  - A manual stub that returns a NOT_IMPLEMENTED response with
    instructions for the support person to walk the user through.

The registry is intentionally tiny in the MVP. ONE end-to-end automated
remediation (`auditd_install`) proves the architecture; everything else
is a stub that returns honest "automation pending" messaging.

Why a registry instead of a switch statement: a registry can be
serialized into the API surface (the frontend can ask "what
remediations exist?" without hardcoding them) and adding a new
remediation is one entry, not a code change in three places. At
enterprise scale the registry would be loaded from a config file or a
database table so non-engineers could add remediations through a
review workflow.
"""

import logging
from typing import Awaitable, Callable, Optional

from .fleet_client import FleetClient, FleetClientError
from .models import RemediationOutcome, RemediationResponse

logger = logging.getLogger(__name__)


# Type alias for a remediation handler. Takes the host_id, returns a
# RemediationResponse. The handler is responsible for any Fleet API
# calls and for translating the result into the response shape.
RemediationHandler = Callable[[FleetClient, int], Awaitable[RemediationResponse]]


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------


async def _auditd_install(client: FleetClient, host_id: int) -> RemediationResponse:
    """Install auditd via apt-get on a Linux host.

    The actual remediation. Runs `apt-get install -y auditd` through
    Fleet's script execution API and translates the result into the
    response shape the frontend renders.

    ASSUMPTION: the host is Debian/Ubuntu with apt-get available. The
    troubleshooter does not currently look at host_platform before
    picking a handler; at enterprise scale the registry key would
    include the platform (e.g. "auditd_install:debian") so the wrong
    handler can't be invoked on a non-matching host.
    """
    # The script is intentionally minimal. apt-get update is needed
    # because Ubuntu Server minimal images often ship with stale apt
    # caches that don't have auditd in the package list. -y avoids the
    # interactive prompt. DEBIAN_FRONTEND=noninteractive prevents the
    # postinstall from blocking on a debconf question that nothing in
    # the script execution context can answer.
    script = (
        "#!/bin/bash\n"
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq\n"
        "apt-get install -y auditd audispd-plugins\n"
        "systemctl enable --now auditd\n"
        "echo 'auditd install complete'\n"
    )

    try:
        result = await client.run_script_sync(host_id, script, timeout_seconds=120)
    except FleetClientError as exc:
        # Fleet's error message is now surfaced verbatim in the exception
        # text by fleet_client._extract_fleet_error_reason. Pass it through
        # to the operator instead of substituting a generic guess. The
        # most useful piece of information for diagnosis is what Fleet
        # actually said, not what we think it might have meant.
        logger.warning("auditd_install fleet error on host %d: %s", host_id, exc)
        return RemediationResponse(
            outcome=RemediationOutcome.FAILED,
            message=(
                f"The remediation could not run. {exc}. "
                "Escalate to engineering with the device hostname."
            ),
        )

    # Fleet's sync script endpoint returns an exit code and the script's
    # combined stdout/stderr. Anything non-zero means the apt-get failed.
    exit_code = result.get("exit_code")
    execution_id = str(result.get("execution_id", ""))

    if exit_code == 0:
        return RemediationResponse(
            outcome=RemediationOutcome.REQUIRES_RECHECK,
            message=(
                "Audit logging package installed. Click Re-check to "
                "confirm Fleet sees the change. The policy should turn "
                "green within a minute."
            ),
            fleet_script_execution_id=execution_id or None,
        )

    # Non-zero exit. Return the script output (or a placeholder) so the
    # operator has something to escalate with.
    output = result.get("output", "(no output captured)")
    return RemediationResponse(
        outcome=RemediationOutcome.FAILED,
        message=(
            f"The install script ran but returned a non-zero exit code "
            f"({exit_code}). Escalate to engineering with this message "
            f"and the device hostname. Script output: {output[:500]}"
        ),
        fleet_script_execution_id=execution_id or None,
    )


async def _not_implemented(
    client: FleetClient,
    host_id: int,
) -> RemediationResponse:
    """Stub handler for remediations that aren't automated yet.

    Returns NOT_IMPLEMENTED so the frontend can render an honest "no
    automation available" message instead of a fake fix button. The
    user-facing translation in translator.py already includes manual
    fix steps for these cases; this stub exists to make the registry
    lookup symmetric.
    """
    return RemediationResponse(
        outcome=RemediationOutcome.NOT_IMPLEMENTED,
        message=(
            "An automated fix for this finding is not available yet. "
            "Follow the manual steps shown above, or escalate to "
            "engineering if you are not comfortable doing so."
        ),
    )


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------

# remediation_id -> handler
REGISTRY: dict[str, RemediationHandler] = {
    "auditd_install": _auditd_install,
    "cramfs_disable": _not_implemented,
    "bootloader_perms": _not_implemented,
    "ipv4_forward_disable": _not_implemented,
}


def get_handler(remediation_id: str) -> Optional[RemediationHandler]:
    """Look up a handler by remediation_id, or None if not registered.

    Routes that need to invoke a remediation should call get_handler
    rather than indexing REGISTRY directly so the None case is explicit
    in the caller.
    """
    return REGISTRY.get(remediation_id)
