"""Plain-English translation layer for Fleet policy failures.

Two paths:

1. **Claude API** (when ANTHROPIC_API_KEY is set). Sends each failing
   policy to Claude with a structured-output prompt that returns JSON
   matching the TranslatedPolicy shape. The prompt forbids technical
   jargon, requires plain-English summary/impact/fix steps, and asks
   for a severity assessment.

2. **Static fallback** (when ANTHROPIC_API_KEY is unset). A hardcoded
   dict mapping policy_name to TranslatedPolicy. Covers the 12 CIS
   policies in gitops/default.yml. Lets the MVP run without an API key
   and serves as the labeled dataset for evaluating Claude's output
   over time.

The translator picks the path automatically based on settings. Code
elsewhere in the backend never knows which path produced a translation.

Why JSON output mode and not text parsing: text parsing is fragile to
prompt drift. Forcing Claude to return JSON via the SDK's tool-use
binding gives the backend a stable contract that doesn't depend on
the model holding a specific output format from one release to the
next.
"""

import json
import logging
from typing import Optional

from .config import Settings
from .models import FleetPolicy, Severity, TranslatedPolicy

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Static fallback dataset
# ----------------------------------------------------------------------
#
# The keys here MUST match the policy names in gitops/default.yml. When
# a new CIS policy is added, an entry should land in this dict at the
# same time. There is no automation enforcing that today; at scale a CI
# check would diff the policy names against the keys here and fail the
# build if they drift.
#
# These translations are also the ground truth for evaluating Claude's
# output. A simple eval (see ADR-0005's "At Enterprise Scale" section)
# would diff Claude's translation of each policy against the static
# version and flag drift over a similarity threshold.

_STATIC_TRANSLATIONS: dict[str, dict] = {
    "CIS 1.1.1.1 cramfs filesystem module disabled": {
        "summary": (
            "An unused legacy filesystem driver is loaded in the device's "
            "kernel. The driver is from the early 2000s and is not used "
            "by anything modern."
        ),
        "impact": (
            "Loaded kernel drivers expand the attack surface even when "
            "they are not in active use. Removing them is a standard "
            "compliance baseline."
        ),
        "fix_steps": [
            "Click the Fix button below to unload the driver.",
            "If the user has a current task in progress, ask them to save it first. The fix is instant and does not interrupt active work in practice.",
        ],
        "severity": Severity.LOW,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,  # Manual stub for now
    },
    "CIS 1.4.1 bootloader config owned by root and restricted": {
        "summary": (
            "The boot configuration file on the device is more permissive "
            "than it should be. Anyone with a regular account on the device "
            "could read it."
        ),
        "impact": (
            "The boot config tells the kernel which security features to "
            "turn on. If a non-administrator can read it, they can find "
            "weaknesses to exploit during a privilege escalation attempt."
        ),
        "fix_steps": [
            "Click the Fix button to tighten the file's permissions.",
            "The change does not require a reboot.",
        ],
        "severity": Severity.MEDIUM,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 3.1.1 IPv4 packet forwarding disabled": {
        "summary": (
            "The device is configured to forward network traffic between "
            "interfaces, like a router. It should not be doing that unless "
            "it is intentionally a router."
        ),
        "impact": (
            "A device that forwards traffic can be used as a pivot point "
            "to reach other devices on the network from somewhere it "
            "should not have access to. Almost always a misconfiguration."
        ),
        "fix_steps": [
            "Click Fix to turn off IP forwarding.",
            "If the device is supposed to be a router (rare for a workstation), do not click Fix and escalate to engineering.",
        ],
        "severity": Severity.HIGH,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 3.5 host firewall module is loaded": {
        "summary": (
            "The host firewall is not active on this device."
        ),
        "impact": (
            "Without an active firewall, every listening service on the "
            "device is reachable from anything that can route to it. "
            "This is a baseline compliance requirement and a real "
            "exposure risk."
        ),
        "fix_steps": [
            "This fix needs an engineer because turning on the firewall on a remote device can drop the active session if rules are wrong.",
            "Escalate to the on-call CPE engineer with the device hostname.",
        ],
        "severity": Severity.HIGH,
        "support_can_fix_themselves": False,
        "escalate_to": "on-call CPE engineer",
        "automated_remediation_id": None,
    },
    "CIS 4.1.1.1 auditd package installed": {
        "summary": (
            "The audit logging package is missing from this device. "
            "Without it, the device cannot keep a tamper-resistant log "
            "of administrative actions."
        ),
        "impact": (
            "Audit logs are a compliance requirement for SOC 2 and most "
            "security frameworks. They are also the first thing incident "
            "response asks for when investigating a suspicious event. "
            "A device without auditd is a blind spot."
        ),
        "fix_steps": [
            "Ask the user to open a terminal on the device.",
            "Have them run: sudo apt-get update && sudo apt-get install -y auditd audispd-plugins",
            "The install takes about 30 seconds and does not require a reboot.",
            "Click Re-check to confirm the package is installed and the policy turns green.",
        ],
        "severity": Severity.MEDIUM,
        "support_can_fix_themselves": True,
        # Automated remediation is intentionally disabled. ADR-0006
        # documents the investigation: Fleet's script execution API
        # requires orbit to report the scripts_enabled capability, which
        # does not reliably populate in self-signed-cert deployments.
        # The manual path in fix_steps above is the reliable fallback.
        "automated_remediation_id": None,
    },
    "CIS 4.2.3 syslog file permissions": {
        "summary": (
            "The system log file on this device is more permissive than "
            "it should be. Other users on the same device could read "
            "authentication and admin events."
        ),
        "impact": (
            "System logs contain sudo invocations, auth attempts, and "
            "service errors. Exposing them to non-administrators makes "
            "credential harvesting and timing attacks easier."
        ),
        "fix_steps": [
            "Click Fix to restrict the log file permissions.",
            "The change is instant and does not affect log writers.",
        ],
        "severity": Severity.MEDIUM,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 5.1.1 cron daemon is active": {
        "summary": (
            "The scheduled task service is not running on this device."
        ),
        "impact": (
            "Several maintenance jobs (log rotation, security update "
            "checks, intrusion detection sweeps) depend on this service. "
            "Without it, the device misses routine cleanup and may fill "
            "up with stale logs."
        ),
        "fix_steps": [
            "Click Fix to start the scheduled task service.",
            "If the service refuses to start, escalate to engineering with the device hostname.",
        ],
        "severity": Severity.LOW,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 5.2.1 sshd_config owned by root and restricted": {
        "summary": (
            "The SSH server's configuration file is more permissive than "
            "it should be. A non-administrator on the device could "
            "modify it."
        ),
        "impact": (
            "An attacker who can modify the SSH config can disable "
            "authentication, weaken ciphers, or open backdoors. This is "
            "the kind of finding that turns a low-privilege foothold "
            "into a full compromise."
        ),
        "fix_steps": [
            "Click Fix to tighten the SSH config file permissions.",
            "The change is instant and does not interrupt active SSH sessions.",
        ],
        "severity": Severity.HIGH,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 5.2.2 SSH host private keys restricted to root": {
        "summary": (
            "The SSH server's private key file is readable by users it "
            "should not be readable by."
        ),
        "impact": (
            "The SSH host private key is the cryptographic identity of "
            "the device. If anyone other than the system administrator "
            "can read it, the device's identity can be impersonated by "
            "a man-in-the-middle attacker."
        ),
        "fix_steps": [
            "Click Fix to restrict the host key permissions.",
            "The next SSH connection from any client may show a host key warning if the underlying key was actually rotated. If users complain about a host key warning, escalate to engineering.",
        ],
        "severity": Severity.HIGH,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 6.1.2 /etc/passwd permissions": {
        "summary": (
            "The user account file on this device has the wrong permissions."
        ),
        "impact": (
            "If the file is more permissive than expected, any user on "
            "the device could modify the account list. If it's less "
            "permissive, normal account lookups break."
        ),
        "fix_steps": [
            "Click Fix to set the correct permissions on the user account file.",
        ],
        "severity": Severity.MEDIUM,
        "support_can_fix_themselves": True,
        "automated_remediation_id": None,
    },
    "CIS 6.1.5 /etc/shadow permissions": {
        "summary": (
            "The password hash file on this device is readable by users "
            "who should not be able to read it."
        ),
        "impact": (
            "This file contains every local account's password hash. "
            "Exposing it lets an attacker run offline password-cracking "
            "tools. A finding here is a serious credential exposure."
        ),
        "fix_steps": [
            "This fix needs an engineer because tightening the password file permissions on the wrong group can break PAM authentication and lock users out.",
            "Escalate to the on-call CPE engineer with the device hostname.",
        ],
        "severity": Severity.CRITICAL,
        "support_can_fix_themselves": False,
        "escalate_to": "on-call CPE engineer",
        "automated_remediation_id": None,
    },
    "CIS 6.2.5 only root has UID 0": {
        "summary": (
            "There is more than one administrator-equivalent account on "
            "this device. There should be exactly one."
        ),
        "impact": (
            "An extra account with full administrator privileges is "
            "either a leftover from a misconfiguration or a backdoor "
            "from a previous compromise. Either way it needs immediate "
            "investigation."
        ),
        "fix_steps": [
            "Do not delete the account yet. Engineering needs to investigate first.",
            "Escalate to the on-call CPE engineer immediately and tag the security team. Include the device hostname.",
        ],
        "severity": Severity.CRITICAL,
        "support_can_fix_themselves": False,
        "escalate_to": "on-call CPE engineer + security team",
        "automated_remediation_id": None,
    },
}


# ----------------------------------------------------------------------
# Public translator interface
# ----------------------------------------------------------------------


class Translator:
    """Translates Fleet policy failures into TranslatedPolicy objects.

    Picks Claude or static fallback once at construction based on
    whether anthropic_api_key is set in settings. The picked path is
    fixed for the lifetime of the instance.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._use_claude = bool(settings.anthropic_api_key)

        # Lazy-init the Anthropic client only when we're actually
        # going to use it. Saves the import cost when running in
        # static-fallback mode.
        self._anthropic = None
        if self._use_claude:
            from anthropic import AsyncAnthropic

            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
            logger.info("translator: Claude API enabled (model=%s)", settings.anthropic_model)
        else:
            logger.info("translator: static fallback mode (no ANTHROPIC_API_KEY)")

    async def translate(
        self,
        policy: FleetPolicy,
        host_platform: str,
        host_os_version: str,
    ) -> TranslatedPolicy:
        """Translate one failing policy into the support-facing form.

        Falls back from Claude to the static dict on any Claude error
        so a transient API outage does not break the support workflow.
        """
        if self._use_claude:
            try:
                return await self._translate_via_claude(
                    policy, host_platform, host_os_version
                )
            except Exception as exc:
                logger.warning(
                    "claude translation failed for %s, falling back to static: %s",
                    policy.name,
                    exc,
                )
                # Fall through to the static path.

        return self._translate_via_static(policy)

    # ------------------------------------------------------------------
    # Static path
    # ------------------------------------------------------------------

    def _translate_via_static(self, policy: FleetPolicy) -> TranslatedPolicy:
        """Look up the policy in the static dict, or build a generic
        'I don't know this policy' response if it's not in the dict.
        """
        entry = _STATIC_TRANSLATIONS.get(policy.name)
        if entry is None:
            # Unknown policy. Return an honest "this needs engineering"
            # message rather than fabricating a translation.
            return TranslatedPolicy(
                policy_id=policy.id,
                policy_name=policy.name,
                summary=(
                    "This device failed a compliance check that the "
                    "Compliance Troubleshooter does not yet recognize."
                ),
                impact=(
                    "Without a translation, support cannot self-serve "
                    "this fix. The finding still appears in Fleet's "
                    "policy dashboard for engineering to triage."
                ),
                fix_steps=[
                    "Escalate to the on-call CPE engineer with the device hostname.",
                    "Mention the policy name in the escalation note.",
                ],
                severity=Severity.MEDIUM,
                support_can_fix_themselves=False,
                escalate_to="on-call CPE engineer",
                automated_remediation_id=None,
            )

        return TranslatedPolicy(
            policy_id=policy.id,
            policy_name=policy.name,
            summary=entry["summary"],
            impact=entry["impact"],
            fix_steps=entry["fix_steps"],
            severity=entry["severity"],
            support_can_fix_themselves=entry["support_can_fix_themselves"],
            escalate_to=entry.get("escalate_to"),
            automated_remediation_id=entry.get("automated_remediation_id"),
        )

    # ------------------------------------------------------------------
    # Claude path
    # ------------------------------------------------------------------

    _SYSTEM_PROMPT = """You are a translator that converts technical compliance findings into clear, non-technical explanations for support staff at a software company.

The support staff are smart but they do not read SQL, do not know what osquery is, and do not know what CIS section numbers mean. Your job is to translate raw findings into language a support person can take action on.

Rules:
- Never mention SQL, osquery, queries, file modes, kernel modules, sysctl values, or any other technical jargon
- Never mention CIS section numbers in the user-visible text
- Use natural device, file, and setting language
- Be honest about severity: a backdoor account is critical, a loaded legacy kernel module is low
- If the fix requires touching production directly or has any risk of breaking the device, mark support_can_fix_themselves as false and recommend escalation

Output ONLY a JSON object with these fields:
- summary: 1-2 plain-english sentences describing what is wrong
- impact: 1 sentence on why this matters (the risk to the business)
- fix_steps: an array of 1-4 ordered steps a support person could follow
- severity: one of "low", "medium", "high", "critical"
- support_can_fix_themselves: boolean
- escalate_to: string identifying who to escalate to if support_can_fix_themselves is false, or null
- automated_remediation_id: string or null - leave null unless the policy is "CIS 4.1.1.1 auditd package installed" in which case use "auditd_install"
"""

    async def _translate_via_claude(
        self,
        policy: FleetPolicy,
        host_platform: str,
        host_os_version: str,
    ) -> TranslatedPolicy:
        """Call Claude with the policy and parse the JSON response."""
        assert self._anthropic is not None  # set in __init__ when use_claude is true

        user_message = (
            f"A device has failed a compliance policy.\n\n"
            f"Device platform: {host_platform}\n"
            f"Device OS version: {host_os_version}\n\n"
            f"Policy name: {policy.name}\n"
            f"Policy description: {policy.description or '(no description)'}\n"
            f"Resolution hint: {policy.resolution or '(no resolution hint)'}\n"
            f"Underlying query (DO NOT show this to the user): {policy.query}\n\n"
            f"Generate the JSON translation now."
        )

        response = await self._anthropic.messages.create(
            model=self._settings.anthropic_model,
            max_tokens=1024,
            system=self._SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Claude returns a list of content blocks; we want the text from
        # the first text block. Anthropic's SDK guarantees the structure.
        text_block = next(
            (b for b in response.content if getattr(b, "type", None) == "text"),
            None,
        )
        if text_block is None:
            raise RuntimeError("Claude response had no text block")

        # The model is instructed to return ONLY JSON. If it wraps the
        # JSON in markdown code fences (which it sometimes does despite
        # instructions), strip them defensively.
        raw = text_block.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            # Drop the optional language tag like "json\n"
            if "\n" in raw:
                raw = raw.split("\n", 1)[1]
            raw = raw.rstrip("`").strip()

        parsed = json.loads(raw)

        return TranslatedPolicy(
            policy_id=policy.id,
            policy_name=policy.name,
            summary=parsed["summary"],
            impact=parsed["impact"],
            fix_steps=parsed["fix_steps"],
            severity=Severity(parsed["severity"]),
            support_can_fix_themselves=parsed["support_can_fix_themselves"],
            escalate_to=parsed.get("escalate_to"),
            automated_remediation_id=parsed.get("automated_remediation_id"),
        )
