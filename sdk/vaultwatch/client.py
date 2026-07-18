"""
VaultWatch Python SDK Client

FIX #19: Added direct contract-query methods:
  - audit_trail.get_finding(id)
  - audit_trail.finding_count()
  - risk_oracle.get_score(address)
  - policy_manager.get_current_policy()
  - sentinel_credit.get_balance(address)
  - agent_behavior.get_score(agent_id)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("vaultwatch.sdk")

# Default contract deploy hashes on Casper testnet
DEFAULT_CONTRACT_HASHES = {
    "AuditTrail": "b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6336a7",
    "SentinelRegistry": "9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c",
    "RiskOracle": "e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d",
    "SentinelCredit": "0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71",
    "AgentBehaviorIndex": "05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0",
    "SentinelAlertLog": "53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925",
    "RiskPolicyManager": "93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e",
    "SubscriberVault": "6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d",
}


class VaultWatchRPCError(Exception):
    """Raised when a Casper RPC call fails."""


class VaultWatchClient:
    """
    VaultWatch Python SDK.

    Provides typed, documented access to all 8 VaultWatch smart contracts
    on Casper testnet.

    Usage::

        from vaultwatch import VaultWatchClient
        client = VaultWatchClient()

        # Get a specific finding by ID
        finding = await client.audit_trail.get_finding(0)

        # Get current risk policy
        policy = await client.policy_manager.get_current_policy()

        # Get credit balance
        balance = await client.sentinel_credit.get_balance("0x...")

    """

    def __init__(
        self,
        rpc_url: str = "",
        contract_hashes: dict = None,
        timeout: float = 15.0,
    ):
        self.rpc_url = rpc_url or os.getenv(
            "CASPER_RPC_URL",
            "https://node.testnet.casper.network/rpc",
        )
        self.hashes = {**DEFAULT_CONTRACT_HASHES, **(contract_hashes or {})}
        self.timeout = timeout

        # Sub-clients for each contract
        self.audit_trail = AuditTrailClient(self)
        self.risk_oracle = RiskOracleClient(self)
        self.policy_manager = RiskPolicyManagerClient(self)
        self.sentinel_credit = SentinelCreditClient(self)
        self.agent_behavior = AgentBehaviorClient(self)
        self.sentinel_registry = SentinelRegistryClient(self)
        self.sentinel_alert_log = SentinelAlertLogClient(self)
        self.subscriber_vault = SubscriberVaultClient(self)

    async def _rpc(
        self, method: str, params: dict | list
    ) -> Any:
        """Execute a Casper JSON-RPC call."""
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.rpc_url, json=body)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise VaultWatchRPCError(
                    f"RPC error: {data['error'].get('message', data['error'])}"
                )
            return data.get("result")

    async def _query_contract(
        self, contract_name: str, path: list
    ) -> Any:
        """Query a named key path on a contract."""
        contract_hash = self.hashes.get(contract_name)
        if not contract_hash:
            raise VaultWatchRPCError(f"Unknown contract: {contract_name}")
        return await self._rpc(
            "state_get_item",
            {"key": f"hash-{contract_hash}", "path": path},
        )

    async def get_chain_state(self) -> dict:
        """Get current Casper testnet block info."""
        result = await self._rpc("chain_get_block", {})
        block = result.get("block", {}).get("header", {})
        return {
            "block_height": block.get("height"),
            "era_id": block.get("era_id"),
            "timestamp": block.get("timestamp"),
            "network": "casper-test",
        }

    async def verify_deploy(self, deploy_hash: str) -> dict:
        """Verify a deploy hash status on Casper testnet."""
        result = await self._rpc(
            "info_get_deploy", {"deploy_hash": deploy_hash}
        )
        exec_results = result.get("execution_results", [])
        success = False
        if exec_results:
            exec_result = exec_results[0].get("result", {})
            success = "Success" in exec_result
        return {
            "deploy_hash": deploy_hash,
            "success": success,
            "block_hash": exec_results[0].get("block_hash") if exec_results else None,
            "explorer_url": f"https://testnet.cspr.live/deploy/{deploy_hash}",
        }


class AuditTrailClient:
    """Direct query methods for the AuditTrail contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_finding(self, finding_id: int) -> dict:
        """Fetch a specific finding by ID from AuditTrail contract.

        FIX #19: Direct contract query method.

        Returns::

            {
                "id": 0,
                "address": "0x...",
                "risk_type": "rug_pull",
                "severity": "CRITICAL",
                "confidence": 95,
                "description": "...",
                "block_height": 12345,
                "timestamp": 1720000000,
            }
        """
        result = await self._sdk._query_contract(
            "AuditTrail", ["findings", str(finding_id)]
        )
        return result or {}

    async def finding_count(self) -> int:
        """Get total number of findings recorded."""
        result = await self._sdk._query_contract(
            "AuditTrail", ["finding_count"]
        )
        return int(result.get("stored_value", {}).get("CLValue", {}).get("parsed", 0))

    async def get_all_findings(self, limit: int = 20) -> list:
        """Fetch the last N findings from the AuditTrail contract."""
        count = await self.finding_count()
        findings = []
        start = max(0, count - limit)
        for i in range(start, count):
            try:
                finding = await self.get_finding(i)
                if finding:
                    findings.append(finding)
            except VaultWatchRPCError:
                break
        return findings


class RiskOracleClient:
    """Direct query methods for the RiskOracle contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_score(self, address: str) -> dict:
        """Get risk score for an address from RiskOracle contract.

        FIX #19: Direct contract query method.
        """
        result = await self._sdk._query_contract(
            "RiskOracle", ["scores", address]
        )
        return result or {"address": address, "score": None, "error": "not_found"}


class RiskPolicyManagerClient:
    """Direct query methods for the RiskPolicyManager contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_current_policy(self) -> dict:
        """Fetch the currently active RiskPolicy from chain.

        FIX #19: Direct contract query method.

        Returns::

            {
                "version": 2,
                "min_confidence_threshold": 75,
                "critical_score_threshold": 80,
                "high_score_threshold": 60,
                "medium_score_threshold": 40,
                "max_retry_count": 2,
                "safety_rejection_threshold": 80,
            }
        """
        result = await self._sdk._query_contract(
            "RiskPolicyManager", ["current_policy"]
        )
        parsed = (
            result.get("stored_value", {})
            .get("CLValue", {})
            .get("parsed", {})
        )
        return parsed or {"version": 1, "source": "default"}

    async def get_policy_version(self, version: int) -> dict:
        """Fetch a historical policy by version number."""
        result = await self._sdk._query_contract(
            "RiskPolicyManager", ["policy_history", str(version)]
        )
        return result or {}


class SentinelCreditClient:
    """Direct query methods for the SentinelCredit contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_balance(self, account_address: str) -> int:
        """Get CSPR credit balance for an account (in motes).

        FIX #19: Direct contract query method.
        """
        result = await self._sdk._query_contract(
            "SentinelCredit", ["accounts", account_address]
        )
        parsed = (
            result.get("stored_value", {})
            .get("CLValue", {})
            .get("parsed", {})
        )
        return int(parsed.get("balance", 0)) if parsed else 0

    async def get_query_price(self) -> int:
        """Get current price per standard query (in motes)."""
        result = await self._sdk._query_contract(
            "SentinelCredit", ["query_price"]
        )
        parsed = (
            result.get("stored_value", {})
            .get("CLValue", {})
            .get("parsed", "0")
        )
        return int(parsed)


class AgentBehaviorClient:
    """Direct query methods for the AgentBehaviorIndex contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_score(self, agent_id: str) -> dict:
        """Get behavior score for a VaultWatch agent.

        FIX #19: Direct contract query method.
        """
        result = await self._sdk._query_contract(
            "AgentBehaviorIndex", ["agent_scores", agent_id]
        )
        return result or {"agent_id": agent_id, "score": None}


class SentinelRegistryClient:
    """Direct query methods for the SentinelRegistry contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def is_registered(self, address: str) -> bool:
        """Check if an address is a registered VaultWatch subscriber."""
        result = await self._sdk._query_contract(
            "SentinelRegistry", ["sentinels", address]
        )
        parsed = (
            result.get("stored_value", {})
            .get("CLValue", {})
            .get("parsed", {})
        )
        return bool(parsed.get("active", False)) if parsed else False


class SentinelAlertLogClient:
    """Direct query methods for the SentinelAlertLog contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_address_logs(self, address: str) -> list:
        """Get all log IDs for a subscriber address."""
        result = await self._sdk._query_contract(
            "SentinelAlertLog", ["address_logs", address]
        )
        parsed = (
            result.get("stored_value", {})
            .get("CLValue", {})
            .get("parsed", [])
        )
        return list(parsed) if parsed else []

    async def get_log(self, log_id: int) -> dict:
        """Get a specific alert log record."""
        result = await self._sdk._query_contract(
            "SentinelAlertLog", ["logs", str(log_id)]
        )
        return result or {}


class SubscriberVaultClient:
    """Direct query methods for the SubscriberVault contract."""

    def __init__(self, sdk: VaultWatchClient):
        self._sdk = sdk

    async def get_vault(self, address: str) -> dict:
        """Get vault info for a subscriber."""
        result = await self._sdk._query_contract(
            "SubscriberVault", ["vaults", address]
        )
        return result or {}
