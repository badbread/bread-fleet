"""Seed the Notion compliance database.

One-shot CLI script that:
1. Creates a Notion database with the compliance schema
2. Pulls real policy failures from the Fleet API
3. Generates realistic simulated historical entries
4. Populates the database with all entries

Usage:
    export NOTION_API_TOKEN=ntn_...
    export NOTION_PAGE_ID=abc123...
    export FLEET_API_URL=https://fleet-server:8080
    export FLEET_API_TOKEN=...
    python seed.py

Outputs the database ID for use in NOTION_DATABASE_ID env var.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

from notion_client import (
    COMPLIANCE_DB_SCHEMA,
    NotionClient,
    prop_date,
    prop_rich_text,
    prop_select,
    prop_title,
    prop_url,
)

load_dotenv()

NOTION_API_TOKEN = os.environ["NOTION_API_TOKEN"]
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID", "")
FLEET_API_URL = os.environ.get("FLEET_API_URL", "")
FLEET_API_TOKEN = os.environ.get("FLEET_API_TOKEN", "")
PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "https://fleet.badbread.com")

# Platform name mapping (Fleet uses lowercase, Notion uses display names)
PLATFORM_MAP = {
    "ubuntu": "Linux",
    "darwin": "macOS",
    "windows": "Windows",
    "ios": "iOS",
    "linux": "Linux",
}

# Static translations for root cause text (subset matching translator.py)
ROOT_CAUSES = {
    "CIS 1.1.1.1 cramfs filesystem module disabled": (
        "An unused legacy filesystem driver is loaded in the kernel. "
        "Standard compliance baseline requires removing it."
    ),
    "CIS 1.4.1 bootloader config owned by root and restricted": (
        "The boot configuration file is more permissive than it should be. "
        "Non-administrators could read kernel boot parameters."
    ),
    "CIS 3.1.1 IPv4 packet forwarding disabled": (
        "The device is forwarding network traffic between interfaces like "
        "a router. Almost always a misconfiguration on workstations."
    ),
    "CIS 3.5 host firewall module is loaded": (
        "No active firewall kernel module. Every listening service is "
        "reachable from the network without filtering."
    ),
    "CIS 4.1.1.1 auditd package installed": (
        "Audit logging package is missing. The device has no "
        "tamper-resistant log of administrative actions."
    ),
    "CIS 4.2.3 syslog file permissions": (
        "System log file permissions are too permissive. Other users "
        "on the device could read authentication events."
    ),
    "CIS 5.1.1 cron daemon is active": (
        "Scheduled task service is not running. Maintenance jobs like "
        "log rotation and security sweeps are not executing."
    ),
    "CIS 5.2.1 sshd_config owned by root and restricted": (
        "SSH server configuration file is writable by non-administrators. "
        "Could be modified to weaken authentication."
    ),
    "CIS 5.2.2 SSH host private keys restricted to root": (
        "SSH host private key is readable by non-root users. The device's "
        "cryptographic identity could be impersonated."
    ),
    "CIS 6.1.2 /etc/passwd permissions": (
        "User account file has incorrect permissions. Could allow "
        "unauthorized modification of account information."
    ),
    "CIS 6.1.5 /etc/shadow permissions": (
        "Password hash file is readable by users who should not see it. "
        "Enables offline password cracking attacks."
    ),
    "CIS 6.2.5 only root has UID 0": (
        "Multiple accounts with full administrator privileges detected. "
        "Possible backdoor or misconfigured LDAP sync."
    ),
    "macOS CIS 2.5.1 FileVault disk encryption enabled": (
        "Disk is not encrypted. Physical access to the device would "
        "expose all files without any authentication."
    ),
    "macOS CIS 2.2.1 firewall enabled": (
        "Built-in firewall is turned off. Network services are exposed "
        "without filtering."
    ),
    "macOS CIS 2.6.4 Gatekeeper enabled": (
        "Gatekeeper is disabled. Unsigned applications can run without "
        "code signature verification."
    ),
    "macOS CIS 1.3.1 System Integrity Protection enabled": (
        "SIP is disabled. The OS-level defense preventing modification "
        "of protected system files is not active."
    ),
    "macOS CIS 2.10.1 screen lock within 5 minutes": (
        "Screen does not lock automatically within 5 minutes. Unattended "
        "device is accessible to anyone nearby."
    ),
    "macOS CIS 2.3.3.1 remote login (SSH) disabled": (
        "Remote Login (SSH) is enabled. Command-line network access "
        "is available, expanding the attack surface."
    ),
    "macOS CIS 1.2.1 automatic updates enabled": (
        "Automatic software updates are turned off. Security patches "
        "will not be applied until someone checks manually."
    ),
    "macOS CIS 6.1.4 guest account disabled": (
        "Guest account is enabled. Anyone can use the device without "
        "credentials, bypassing per-user audit trails."
    ),
}


async def fetch_fleet_hosts(fleet_url: str, fleet_token: str) -> list[dict]:
    """Pull all hosts from Fleet with their policy results."""
    # verify=False: Fleet LAN instance uses a self-signed cert (ADR-0003).
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        resp = await client.get(
            f"{fleet_url}/api/latest/fleet/hosts",
            headers={"Authorization": f"Bearer {fleet_token}"},
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return resp.json().get("hosts", [])


async def fetch_host_policies(
    fleet_url: str, fleet_token: str, host_id: int
) -> list[dict]:
    """Pull policy results for a specific host."""
    # verify=False: Fleet LAN instance uses a self-signed cert (ADR-0003).
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        resp = await client.get(
            f"{fleet_url}/api/latest/fleet/hosts/{host_id}",
            headers={"Authorization": f"Bearer {fleet_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("host", {}).get("policies", [])


def build_row(
    device: str,
    platform: str,
    policy: str,
    severity: str,
    root_cause: str,
    remediation: str,
    status: str,
    resolved_by: str,
    timestamp: str,
    source_url: str,
) -> dict:
    """Build a Notion page properties dict for one compliance entry."""
    return {
        "Device": prop_title(device),
        "Platform": prop_select(platform),
        "Failed Policy": prop_rich_text(policy),
        "Severity": prop_select(severity),
        "Root Cause": prop_rich_text(root_cause),
        "Remediation": prop_rich_text(remediation),
        "Status": prop_select(status),
        "Resolved By": prop_rich_text(resolved_by),
        "Timestamp": prop_date(timestamp),
        "Source": prop_url(source_url),
    }


def generate_simulated_entries(portal_url: str) -> list[dict]:
    """Generate ~25 realistic historical entries spanning 3 weeks.

    The entries tell a story: initial CIS rollout found lots of issues,
    bulk remediation fixed most of them, a new policy deployment caused
    a dip, and recent findings are still being worked.
    """
    now = datetime.now(timezone.utc)
    entries = []

    # Week 1: Initial CIS rollout (21-14 days ago). Mostly fixed.
    week1 = [
        ("lab-linux-01", "Linux", "CIS 4.1.1.1 auditd package installed", "Medium",
         ROOT_CAUSES.get("CIS 4.1.1.1 auditd package installed", ""),
         "Installed auditd via apt-get. Service started and logging.",
         "Fixed", "Support (manual steps)"),
        ("lab-linux-02", "Linux", "CIS 4.1.1.1 auditd package installed", "Medium",
         ROOT_CAUSES.get("CIS 4.1.1.1 auditd package installed", ""),
         "Installed auditd via apt-get. Service started and logging.",
         "Fixed", "Support (manual steps)"),
        ("lab-linux-01", "Linux", "CIS 1.1.1.1 cramfs filesystem module disabled", "Low",
         ROOT_CAUSES.get("CIS 1.1.1.1 cramfs filesystem module disabled", ""),
         "Unloaded cramfs module and added modprobe blacklist.",
         "Fixed", "Automated remediation"),
        ("lab-linux-02", "Linux", "CIS 1.1.1.1 cramfs filesystem module disabled", "Low",
         ROOT_CAUSES.get("CIS 1.1.1.1 cramfs filesystem module disabled", ""),
         "Unloaded cramfs module and added modprobe blacklist.",
         "Fixed", "Automated remediation"),
        ("eng-mbp-042", "macOS", "macOS CIS 2.2.1 firewall enabled", "Critical",
         ROOT_CAUSES.get("macOS CIS 2.2.1 firewall enabled", ""),
         "User enabled firewall through System Settings with support guidance.",
         "Fixed", "Support (manual steps)"),
        ("eng-mbp-017", "macOS", "macOS CIS 2.5.1 FileVault disk encryption enabled", "Critical",
         ROOT_CAUSES.get("macOS CIS 2.5.1 FileVault disk encryption enabled", ""),
         "FileVault enabled. Encryption completed overnight.",
         "Fixed", "Support (manual steps)"),
        ("srv-ubuntu-003", "Linux", "CIS 6.1.5 /etc/shadow permissions", "Critical",
         ROOT_CAUSES.get("CIS 6.1.5 /etc/shadow permissions", ""),
         "Permissions corrected by CPE engineer during server hardening sprint.",
         "Fixed", "CPE Engineer (escalation)"),
        ("eng-mbp-042", "macOS", "macOS CIS 2.10.1 screen lock within 5 minutes", "Medium",
         ROOT_CAUSES.get("macOS CIS 2.10.1 screen lock within 5 minutes", ""),
         "User adjusted screen lock timeout in System Settings.",
         "Fixed", "Support (manual steps)"),
    ]
    for i, entry in enumerate(week1):
        ts = (now - timedelta(days=21 - i)).isoformat()
        entries.append(build_row(
            *entry, timestamp=ts,
            source_url=f"{portal_url}/compliance/",
        ))

    # Week 2: New SSH key-only policy deployed (14-7 days ago). Mixed status.
    week2 = [
        ("lab-linux-01", "Linux", "CIS 5.2.1 sshd_config owned by root and restricted", "High",
         ROOT_CAUSES.get("CIS 5.2.1 sshd_config owned by root and restricted", ""),
         "Permissions tightened to 0600.",
         "Fixed", "Automated remediation"),
        ("srv-ubuntu-009", "Linux", "CIS 3.5 host firewall module is loaded", "High",
         ROOT_CAUSES.get("CIS 3.5 host firewall module is loaded", ""),
         "Escalated to CPE. Firewall enablement requires network rule review.",
         "Escalated", ""),
        ("eng-mbp-023", "macOS", "macOS CIS 2.6.4 Gatekeeper enabled", "High",
         ROOT_CAUSES.get("macOS CIS 2.6.4 Gatekeeper enabled", ""),
         "Re-enabled Gatekeeper via spctl --master-enable.",
         "Fixed", "Support (manual steps)"),
        ("eng-mbp-088", "macOS", "macOS CIS 1.3.1 System Integrity Protection enabled", "High",
         ROOT_CAUSES.get("macOS CIS 1.3.1 System Integrity Protection enabled", ""),
         "Escalated. Requires Recovery Mode boot to re-enable SIP.",
         "Escalated", ""),
        ("lab-linux-02", "Linux", "CIS 3.1.1 IPv4 packet forwarding disabled", "High",
         ROOT_CAUSES.get("CIS 3.1.1 IPv4 packet forwarding disabled", ""),
         "Disabled IP forwarding via sysctl.",
         "Fixed", "Automated remediation"),
        ("srv-ubuntu-017", "Linux", "CIS 4.2.3 syslog file permissions", "Medium",
         ROOT_CAUSES.get("CIS 4.2.3 syslog file permissions", ""),
         "Corrected syslog permissions to 0640.",
         "Fixed", "Support (one-click fix)"),
        ("eng-mbp-055", "macOS", "macOS CIS 2.3.3.1 remote login (SSH) disabled", "Medium",
         ROOT_CAUSES.get("macOS CIS 2.3.3.1 remote login (SSH) disabled", ""),
         "Developer needs SSH for work. Policy exception filed.",
         "In Progress", ""),
        ("corp-win-004", "Windows", "CIS 3.5 host firewall module is loaded", "High",
         "Windows Defender Firewall service is stopped. Network services "
         "are exposed without packet filtering.",
         "IT re-enabled Windows Firewall via Group Policy push.",
         "Fixed", "CPE Engineer (escalation)"),
        ("eng-mbp-071", "macOS", "macOS CIS 1.2.1 automatic updates enabled", "Medium",
         ROOT_CAUSES.get("macOS CIS 1.2.1 automatic updates enabled", ""),
         "User re-enabled automatic updates in System Settings.",
         "Fixed", "Support (manual steps)"),
        ("srv-ubuntu-012", "Linux", "CIS 5.1.1 cron daemon is active", "Low",
         ROOT_CAUSES.get("CIS 5.1.1 cron daemon is active", ""),
         "Started and enabled cron service via systemctl.",
         "Fixed", "Support (one-click fix)"),
    ]
    for i, entry in enumerate(week2):
        ts = (now - timedelta(days=14 - i)).isoformat()
        entries.append(build_row(
            *entry, timestamp=ts,
            source_url=f"{portal_url}/compliance/",
        ))

    # Week 3: Recent findings (7-1 days ago). Pending and in progress.
    week3 = [
        ("eng-mbp-092", "macOS", "macOS CIS 2.5.1 FileVault disk encryption enabled", "Critical",
         ROOT_CAUSES.get("macOS CIS 2.5.1 FileVault disk encryption enabled", ""),
         "Contacted user. Awaiting device return from travel.",
         "In Progress", ""),
        ("srv-ubuntu-022", "Linux", "CIS 6.2.5 only root has UID 0", "Critical",
         ROOT_CAUSES.get("CIS 6.2.5 only root has UID 0", ""),
         "Escalated immediately. Security team investigating.",
         "Escalated", ""),
        ("lab-linux-01", "Linux", "CIS 4.2.3 syslog file permissions", "Medium",
         ROOT_CAUSES.get("CIS 4.2.3 syslog file permissions", ""),
         "Identified during routine compliance check. Awaiting fix.",
         "Pending", ""),
        ("eng-mbp-033", "macOS", "macOS CIS 6.1.4 guest account disabled", "Low",
         ROOT_CAUSES.get("macOS CIS 6.1.4 guest account disabled", ""),
         "Guest account found enabled on shared conference room Mac.",
         "Pending", ""),
        ("lab-linux-02", "Linux", "CIS 1.4.1 bootloader config owned by root and restricted", "Medium",
         ROOT_CAUSES.get("CIS 1.4.1 bootloader config owned by root and restricted", ""),
         "Scheduled for next maintenance window.",
         "In Progress", ""),
    ]
    for i, entry in enumerate(week3):
        ts = (now - timedelta(days=7 - i)).isoformat()
        entries.append(build_row(
            *entry, timestamp=ts,
            source_url=f"{portal_url}/compliance/",
        ))

    return entries


async def main() -> None:
    notion = NotionClient(NOTION_API_TOKEN)

    try:
        # Step 1: Create the database (or use existing one)
        existing_db_id = os.environ.get("NOTION_DATABASE_ID")
        if existing_db_id:
            db_id = existing_db_id
            print(f"Using existing database: {db_id}")
        else:
            print("Creating Notion database...")
            db_id = await notion.create_database(
                page_id=NOTION_PAGE_ID,
                title="Fleet Compliance Remediation Log",
                properties=COMPLIANCE_DB_SCHEMA,
            )
            print(f"Database created: {db_id}")

        # Step 2: Pull real Fleet data
        real_entries = []
        if FLEET_API_TOKEN:
            print("Fetching real Fleet host data...")
            hosts = await fetch_fleet_hosts(FLEET_API_URL, FLEET_API_TOKEN)
            print(f"Found {len(hosts)} hosts")

            for host in hosts:
                hostname = host.get("hostname", "unknown")
                platform = PLATFORM_MAP.get(host.get("platform", ""), host.get("platform", ""))
                policies = await fetch_host_policies(
                    FLEET_API_URL, FLEET_API_TOKEN, host["id"]
                )

                for p in policies:
                    if p.get("response") == "fail":
                        policy_name = p.get("name", "Unknown policy")
                        root_cause = ROOT_CAUSES.get(
                            policy_name,
                            f"Device failed compliance check: {policy_name}"
                        )
                        real_entries.append(build_row(
                            device=hostname,
                            platform=platform,
                            policy=policy_name,
                            severity="High",  # Default, real severity comes from translator
                            root_cause=root_cause,
                            remediation="Identified by automated compliance scan. Awaiting remediation.",
                            status="Pending",
                            resolved_by="",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            source_url=f"{PORTAL_BASE_URL}/compliance/",
                        ))

            print(f"Found {len(real_entries)} real policy failures")
        else:
            print("No FLEET_API_TOKEN set, skipping real Fleet data")

        # Step 3: Generate simulated historical entries
        print("Generating simulated historical entries...")
        sim_entries = generate_simulated_entries(PORTAL_BASE_URL)
        print(f"Generated {len(sim_entries)} simulated entries")

        # Step 4: Populate the database (simulated first, then real, so
        # real entries appear at the top of the default sort)
        all_entries = sim_entries + real_entries
        print(f"Populating database with {len(all_entries)} entries...")

        for i, entry in enumerate(all_entries):
            await notion.create_page(db_id, entry)
            # Conservative pacing to avoid Cloudflare WAF blocks.
            # Notion's API allows 3 req/s but Cloudflare's bot detection
            # triggers on rapid sequential POST requests from the same IP.
            # 3s between requests is slow but reliable.
            await asyncio.sleep(3.0)
            if (i + 1) % 5 == 0:
                print(f"  {i + 1}/{len(all_entries)} entries created")

        print(f"\nDone. {len(all_entries)} entries created.")
        print(f"\nNOTION_DATABASE_ID={db_id}")
        print("\nAdd this to your portal/.env and troubleshooter config.")
        print("Then share the Notion page publicly (Share > Publish to web).")

    finally:
        await notion.close()


if __name__ == "__main__":
    asyncio.run(main())
