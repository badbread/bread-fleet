"""Pydantic models for the security posture dashboard API.

These define the response shapes the frontend consumes. In production,
the data behind these models comes from Fleet's REST API with periodic
snapshots in Postgres. In the demo, it comes from synthetic.py which
generates a deterministic 150-device fleet from seed_data.json.
"""

from typing import Literal

from pydantic import BaseModel

Severity = Literal["low", "medium", "high", "critical"]


class PlatformSummary(BaseModel):
    platform: str
    device_count: int
    fully_compliant: int
    health_score: float


class PostureSummary(BaseModel):
    """Fleet-wide health at a glance. The health_score is weighted:
    critical policy failures count 4x, high 3x, medium 2x, low 1x.
    This surfaces what actually matters instead of treating a missing
    NTP config the same as a missing disk encryption."""
    health_score: float
    device_count: int
    total_checks: int
    platforms: list[PlatformSummary]


class TrendPoint(BaseModel):
    date: str
    health_score: float
    device_count: int
    events: list[str]


class PolicyRanking(BaseModel):
    policy_id: int
    name: str
    severity: Severity
    weight: int
    fail_count: int
    pass_count: int
    applicable_count: int
    fail_rate: float


class DeviceRisk(BaseModel):
    hostname: str
    platform: str
    os_version: str
    last_seen: str
    fail_count: int
    total_policies: int
    risk_score: int


class PolicyDevice(BaseModel):
    hostname: str
    platform: str
    os_version: str
    last_seen: str
