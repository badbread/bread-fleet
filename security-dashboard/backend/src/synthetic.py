"""Synthetic fleet data generator.

Produces a realistic-looking 150-device enterprise fleet from the seed
data in seed_data.json. The seed defines policies and 30-day trend
snapshots; this module generates per-device records with deterministic
pass/fail distributions shaped to tell a believable compliance story.

In production, this entire module goes away. The data comes from Fleet's
REST API with periodic snapshots stored in Postgres. The synthetic layer
exists because the demo Fleet instance has 2 real hosts, which is not
enough to demonstrate fleet-wide posture visibility. The seed data is
designed to be honest about this (the portal landing page says
"augmented data") while still showing the architecture and the thinking.

Why deterministic: random data looks random. Real compliance data has
patterns (patch lag clusters around release dates, new policies cause
dips, certain device groups are consistently worse). The seed shapes
those patterns intentionally so the charts tell a story a viewer can
follow.
"""

import json
import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Load seed data once at import time. The file is small (<10KB) and
# never changes at runtime.
_SEED_PATH = Path(__file__).parent / "seed_data.json"
with open(_SEED_PATH) as f:
    _SEED = json.load(f)

POLICIES: list[dict[str, Any]] = _SEED["policies"]
SNAPSHOTS: list[dict[str, Any]] = _SEED["snapshots"]

# Policy lookup by ID for fast access.
_POLICY_BY_ID = {p["id"]: p for p in POLICIES}


def _deterministic_fail(device_name: str, policy_id: int, base_rate: float) -> bool:
    """Decide whether a device fails a policy using a stable hash.

    Uses the device name + policy ID as a hash seed so the same device
    always fails the same policies across page loads. The base_rate
    controls how many devices fail fleet-wide (0.0 = nobody fails,
    1.0 = everybody fails). Specific devices are pushed toward failing
    more by their index (higher-numbered devices are newer enrollments
    with more issues).
    """
    h = hashlib.sha256(f"{device_name}:{policy_id}".encode()).hexdigest()
    # Convert first 8 hex chars to a float in [0, 1).
    threshold = int(h[:8], 16) / 0xFFFFFFFF
    return threshold < base_rate


# Failure rates per policy. Shaped to match real-world patterns:
# OS updates lag everywhere, encryption is usually enforced early,
# new policies (SSH key-only) have high initial failure rates.
_FAILURE_RATES: dict[int, float] = {
    1: 0.04,   # full_disk_encryption -- most orgs enforce this early
    2: 0.06,   # firewall_enabled -- usually on by default, a few stragglers
    3: 0.28,   # os_version_current -- patch lag is universal
    4: 0.22,   # ssh_key_only -- recently deployed, many haven't switched
    5: 0.03,   # gatekeeper_enabled -- rarely disabled on managed Macs
    6: 0.15,   # auditd_running -- some servers miss it during provisioning
    7: 0.12,   # automatic_updates -- users disable this, IT re-enables in waves
    8: 0.18,   # screen_lock_timeout -- engineers push back, compliance wins slowly
    9: 0.08,   # remote_login_disabled -- mostly caught during enrollment
    10: 0.02,  # sip_enabled -- almost never disabled on managed devices
    11: 0.10,  # bluetooth_sharing_disabled -- low priority, slow rollout
    12: 0.05,  # guest_account_disabled -- usually part of the base image
    13: 0.03,  # ntp_configured -- almost always on by default
    14: 0.09,  # password_complexity -- some legacy accounts grandfathered in
    15: 0.14,  # usb_storage_restricted -- enforcement in progress
}

# Device definitions. Three fleet segments with different characteristics.
_DEVICES: list[dict[str, Any]] = []


def _build_devices() -> list[dict[str, Any]]:
    """Build the full device list with per-device policy results."""
    if _DEVICES:
        return _DEVICES

    devices = []

    # macOS engineering fleet: 100 laptops, generally well-managed.
    for i in range(1, 101):
        name = f"eng-mbp-{i:03d}"
        # Newer devices (higher index) are slightly more likely to fail
        # because they enrolled more recently and haven't been fully
        # remediated yet.
        age_factor = 1.0 + (i / 100) * 0.3
        devices.append(_make_device(
            hostname=name,
            platform="darwin",
            os_version="macOS 15.4" if i < 75 else "macOS 15.3.1",
            enrolled_days_ago=180 - i,
            last_seen_hours_ago=i % 24,
            age_factor=age_factor,
        ))

    # Ubuntu infrastructure servers: 30, mixed compliance.
    for i in range(1, 31):
        name = f"srv-ubuntu-{i:03d}"
        age_factor = 1.0 + (i / 30) * 0.5
        devices.append(_make_device(
            hostname=name,
            platform="ubuntu",
            os_version="Ubuntu 24.04.2 LTS" if i < 22 else "Ubuntu 22.04.5 LTS",
            enrolled_days_ago=120 - i,
            last_seen_hours_ago=i % 6,
            age_factor=age_factor,
        ))

    # Windows corporate desktops: 20, generally less automated.
    for i in range(1, 21):
        name = f"corp-win-{i:03d}"
        age_factor = 1.0 + (i / 20) * 0.6
        devices.append(_make_device(
            hostname=name,
            platform="windows",
            os_version="Windows 11 23H2" if i < 14 else "Windows 11 22H2",
            enrolled_days_ago=90 - i,
            last_seen_hours_ago=i % 48,
            age_factor=age_factor,
        ))

    # Two real Fleet hosts, seeded in for honesty. These would come from
    # Fleet's API in production but are hardcoded here so the synthetic
    # data includes them.
    devices.append(_make_device(
        hostname="lab-linux-01",
        platform="ubuntu",
        os_version="Ubuntu 24.04.2 LTS",
        enrolled_days_ago=30,
        last_seen_hours_ago=0,
        age_factor=1.0,
    ))
    devices.append(_make_device(
        hostname="lab-linux-02",
        platform="ubuntu",
        os_version="Ubuntu 24.04.2 LTS",
        enrolled_days_ago=28,
        last_seen_hours_ago=0,
        age_factor=1.0,
    ))

    _DEVICES.extend(devices)
    return _DEVICES


def _make_device(
    hostname: str,
    platform: str,
    os_version: str,
    enrolled_days_ago: int,
    last_seen_hours_ago: int,
    age_factor: float,
) -> dict[str, Any]:
    """Create a single device record with policy results."""
    today = date.today()
    policy_results = []
    for p in POLICIES:
        if platform not in p["platforms"]:
            continue
        rate = _FAILURE_RATES.get(p["id"], 0.1) * age_factor
        failed = _deterministic_fail(hostname, p["id"], min(rate, 0.95))
        policy_results.append({
            "policy_id": p["id"],
            "response": "fail" if failed else "pass",
        })

    return {
        "hostname": hostname,
        "platform": platform,
        "os_version": os_version,
        "enrolled_date": str(today - timedelta(days=max(enrolled_days_ago, 1))),
        "last_seen": str(today - timedelta(hours=last_seen_hours_ago)),
        "policy_results": policy_results,
    }


# ------------------------------------------------------------------
# Public query functions used by the API routes
# ------------------------------------------------------------------


def get_summary() -> dict[str, Any]:
    """Fleet-wide posture summary: health score, device counts, platform split."""
    devices = _build_devices()
    total_checks = 0
    weighted_passes = 0
    weighted_total = 0
    platform_stats: dict[str, dict[str, int]] = {}

    for d in devices:
        plat = d["platform"]
        if plat not in platform_stats:
            platform_stats[plat] = {"total": 0, "passing_all": 0}
        platform_stats[plat]["total"] += 1

        device_all_pass = True
        for pr in d["policy_results"]:
            policy = _POLICY_BY_ID[pr["policy_id"]]
            w = policy["weight"]
            total_checks += 1
            weighted_total += w
            if pr["response"] == "pass":
                weighted_passes += w
            else:
                device_all_pass = False

        if device_all_pass:
            platform_stats[plat]["passing_all"] += 1

    health_score = round((weighted_passes / weighted_total) * 100, 1) if weighted_total else 0

    platforms = []
    for plat, stats in sorted(platform_stats.items()):
        plat_devices = [d for d in devices if d["platform"] == plat]
        plat_weighted_pass = 0
        plat_weighted_total = 0
        for d in plat_devices:
            for pr in d["policy_results"]:
                p = _POLICY_BY_ID[pr["policy_id"]]
                plat_weighted_total += p["weight"]
                if pr["response"] == "pass":
                    plat_weighted_pass += p["weight"]
        plat_score = round((plat_weighted_pass / plat_weighted_total) * 100, 1) if plat_weighted_total else 0
        platforms.append({
            "platform": plat,
            "device_count": stats["total"],
            "fully_compliant": stats["passing_all"],
            "health_score": plat_score,
        })

    return {
        "health_score": health_score,
        "device_count": len(devices),
        "total_checks": total_checks,
        "platforms": platforms,
    }


def get_trend(days: int = 30) -> list[dict[str, Any]]:
    """Historical compliance trend from seed snapshots."""
    return SNAPSHOTS[-days:]


def get_policies_ranked() -> list[dict[str, Any]]:
    """All policies ranked by fleet-wide failure rate, with severity."""
    devices = _build_devices()
    policy_stats: dict[int, dict[str, int]] = {}

    for d in devices:
        for pr in d["policy_results"]:
            pid = pr["policy_id"]
            if pid not in policy_stats:
                policy_stats[pid] = {"pass": 0, "fail": 0}
            policy_stats[pid][pr["response"]] += 1

    result = []
    for p in POLICIES:
        stats = policy_stats.get(p["id"], {"pass": 0, "fail": 0})
        total = stats["pass"] + stats["fail"]
        fail_rate = round((stats["fail"] / total) * 100, 1) if total else 0
        result.append({
            "policy_id": p["id"],
            "name": p["display_name"],
            "severity": p["severity"],
            "weight": p["weight"],
            "fail_count": stats["fail"],
            "pass_count": stats["pass"],
            "applicable_count": total,
            "fail_rate": fail_rate,
        })

    result.sort(key=lambda x: x["fail_rate"], reverse=True)
    return result


def get_policy_devices(policy_id: int) -> list[dict[str, Any]]:
    """Devices failing a specific policy."""
    devices = _build_devices()
    failing = []
    for d in devices:
        for pr in d["policy_results"]:
            if pr["policy_id"] == policy_id and pr["response"] == "fail":
                failing.append({
                    "hostname": d["hostname"],
                    "platform": d["platform"],
                    "os_version": d["os_version"],
                    "last_seen": d["last_seen"],
                })
                break
    return failing


def get_devices_by_risk() -> list[dict[str, Any]]:
    """All devices ranked by weighted failure count (risk score)."""
    devices = _build_devices()
    result = []
    for d in devices:
        risk_score = 0
        fail_count = 0
        total_applicable = len(d["policy_results"])
        for pr in d["policy_results"]:
            if pr["response"] == "fail":
                fail_count += 1
                risk_score += _POLICY_BY_ID[pr["policy_id"]]["weight"]
        result.append({
            "hostname": d["hostname"],
            "platform": d["platform"],
            "os_version": d["os_version"],
            "last_seen": d["last_seen"],
            "fail_count": fail_count,
            "total_policies": total_applicable,
            "risk_score": risk_score,
        })
    result.sort(key=lambda x: x["risk_score"], reverse=True)
    return result
