#!/usr/bin/env python3
"""
VaultWatch — Contract Deployment Script
Deploys all 8 Odra contracts to the Casper network.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from casper_client import CasperContractClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deploy_contracts")

# Contract deploy order (dependencies first)
CONTRACTS = [
    {
        "name": "AuditTrail",
        "wasm": "wasm/AuditTrail.wasm",
        "env_key": "AUDIT_TRAIL_HASH",
        "payment": 120_000_000_000,
        "args": {},
    },
    {
        "name": "RiskOracle",
        "wasm": "wasm/RiskOracle.wasm",
        "env_key": "RISK_ORACLE_HASH",
        "payment": 120_000_000_000,
        "args": {},
    },
    {
        "name": "SentinelCredit",
        "wasm": "wasm/SentinelCredit.wasm",
        "env_key": "SENTINEL_CREDIT_HASH",
        "payment": 150_000_000_000,
        "args": {"name": "SentinelCredit", "symbol": "SRC", "decimals": 9},
    },
    {
        "name": "SentinelRegistry",
        "wasm": "wasm/SentinelRegistry.wasm",
        "env_key": "SENTINEL_REGISTRY_HASH",
        "payment": 130_000_000_000,
        "args": {},
    },
    {
        "name": "SentinelAlertLog",
        "wasm": "wasm/SentinelAlertLog.wasm",
        "env_key": "SENTINEL_ALERT_LOG_HASH",
        "payment": 120_000_000_000,
        "args": {},
    },
    {
        "name": "AgentBehaviorIndex",
        "wasm": "wasm/AgentBehaviorIndex.wasm",
        "env_key": "AGENT_BEHAVIOR_INDEX_HASH",
        "payment": 130_000_000_000,
        "args": {},
    },
    {
        "name": "RiskPolicyManager",
        "wasm": "wasm/RiskPolicyManager.wasm",
        "env_key": "RISK_POLICY_MANAGER_HASH",
        "payment": 130_000_000_000,
        "args": {},
    },
    {
        "name": "SubscriberVault",
        "wasm": "wasm/SubscriberVault.wasm",
        "env_key": "SUBSCRIBER_VAULT_HASH",
        "payment": 140_000_000_000,
        "args": {},
    },
]


def load_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def deploy_all(
    client: CasperContractClient,
    contracts_dir: Path,
    output_file: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, str]:
    """Deploy all contracts and return a map of {name: deploy_hash}."""
    results: Dict[str, str] = {}

    for contract in CONTRACTS:
        wasm_path = contracts_dir / contract["wasm"]
        name = contract["name"]

        if not wasm_path.exists() and not client.mock:
            logger.warning("WASM not found: %s — skipping %s", wasm_path, name)
            continue

        logger.info("Deploying %s...", name)

        if dry_run:
            logger.info("[DRY RUN] Would deploy %s from %s", name, wasm_path)
            results[name] = f"dry-run-hash-{name.lower()}"
            continue

        try:
            deploy_hash = client.deploy_contract(
                wasm_path=str(wasm_path),
                args=contract["args"],
                payment_amount=contract["payment"],
            )
            logger.info("%s deployed — hash: %s", name, deploy_hash)
            results[name] = deploy_hash

            # Wait for inclusion
            if not client.mock:
                logger.info("Waiting for %s to be included in a block...", name)
                success = client.wait_for_deploy(deploy_hash, timeout=120)
                if not success:
                    logger.error("%s deploy timed out!", name)
                    continue
                logger.info("%s included!", name)

        except Exception as exc:
            logger.error("Failed to deploy %s: %s", name, exc)
            results[name] = f"FAILED: {exc}"

    # Write output
    if output_file:
        with open(output_file, "w") as fh:
            json.dump(results, fh, indent=2)
        logger.info("Deploy results written to %s", output_file)

    # Print summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    for name, hash_val in results.items():
        status = "OK" if not hash_val.startswith("FAILED") else "FAIL"
        print(f"  [{status}] {name:<25} {hash_val[:32]}...")
    print("=" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy VaultWatch contracts to Casper")
    parser.add_argument("--contracts-dir", default="contracts", help="Contracts directory")
    parser.add_argument("--output", default="deploy_hashes.json", help="Output file for deploy hashes")
    parser.add_argument("--mock", action="store_true", default=False, help="Mock mode (no live node)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run — no deploys")
    args = parser.parse_args()

    load_dotenv()

    contracts_dir = Path(args.contracts_dir)
    if not contracts_dir.exists():
        contracts_dir = Path(__file__).parent.parent / "contracts"

    use_mock = args.mock or os.getenv("CASPER_MOCK", "true").lower() == "true"
    client = CasperContractClient(mock=use_mock)

    logger.info("VaultWatch Contract Deployer")
    logger.info(
        "Node: %s | Mock: %s | Chain: %s",
        client.node_url,
        client.mock,
        client.chain_name,
    )

    deploy_all(client, contracts_dir, output_file=args.output, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
