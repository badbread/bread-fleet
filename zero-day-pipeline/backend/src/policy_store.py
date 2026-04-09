"""Local JSON policy store for deployed KEV detection policies.

In the demo deployment, this replaces live Fleet API calls for policy
management. Deployed policies are stored in a JSON file on the audit
volume and simulated host results are generated for the two enrolled
lab hosts.

In production, this module is replaced by the Fleet REST API client
(fleet_client.py). The API shapes are identical so the frontend
doesn't change.
"""

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import DeployedPolicy, HostResult

logger = logging.getLogger(__name__)

# Simulated enrolled hosts. In production, these come from Fleet's
# /api/latest/fleet/hosts endpoint.
_SIMULATED_HOSTS = [
    {"hostname": "lab-linux-01", "platform": "ubuntu"},
    {"hostname": "lab-linux-02", "platform": "ubuntu"},
]

_next_id = 1000


class PolicyStore:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._policies: dict[int, DeployedPolicy] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for item in data:
                    p = DeployedPolicy.model_validate(item)
                    if p.fleet_policy_id is not None:
                        self._policies[p.fleet_policy_id] = p
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("failed to load policy store: %s", exc)

    def _save(self) -> None:
        try:
            data = [p.model_dump() for p in self._policies.values()]
            self._path.write_text(json.dumps(data, indent=2))
        except OSError as exc:
            logger.warning("failed to save policy store: %s", exc)

    def deploy(
        self,
        *,
        cve_id: str,
        policy_name: str,
        osquery_sql: str,
        platform: str = "linux",
    ) -> DeployedPolicy:
        """Simulate deploying a policy to Fleet."""
        global _next_id
        policy_id = _next_id
        _next_id += 1

        # Simulate host evaluation. Most hosts pass (the vulnerable
        # package is not installed); occasionally one fails to make
        # the demo interesting.
        host_results = []
        for host in _SIMULATED_HOSTS:
            # Use a deterministic-ish result based on CVE + hostname
            # so the same CVE always shows the same results.
            seed = hash(f"{cve_id}:{host['hostname']}") % 100
            status = "fail" if seed < 30 else "pass"
            host_results.append(HostResult(
                hostname=host["hostname"],
                status=status,
            ))

        deployed = DeployedPolicy(
            cve_id=cve_id,
            fleet_policy_id=policy_id,
            policy_name=policy_name,
            osquery_sql=osquery_sql,
            deployed_at=datetime.now(timezone.utc).isoformat(),
            dry_run=False,
            host_results=host_results,
        )
        self._policies[policy_id] = deployed
        self._save()
        return deployed

    def list_policies(self) -> list[DeployedPolicy]:
        return list(self._policies.values())

    def get_results(self, policy_id: int) -> Optional[list[HostResult]]:
        p = self._policies.get(policy_id)
        if p:
            return p.host_results
        return None

    def delete(self, policy_id: int) -> bool:
        if policy_id in self._policies:
            del self._policies[policy_id]
            self._save()
            return True
        return False
