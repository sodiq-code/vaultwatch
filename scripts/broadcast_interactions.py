#!/usr/bin/env python3
"""
VaultWatch — Broadcast contract interaction TXs to Casper testnet.

Submits 17 calls across all 8 deployed contracts via Casper RPC.
All entry points match the ACTUAL Rust contract definitions.

FIX #1:  Corrected all entry points and argument signatures to match Rust contracts
FIX #6:  Removed hardcoded CSPR.cloud API key — now reads from CASPER_API_KEY env var

Outputs proof/interaction_hashes.json with verified markers.
"""

from __future__ import annotations
import json
import os
import sys
import time
import logging
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("broadcast_interactions")

ROOT = Path(__file__).parent.parent
KEY_PATH = ROOT / "secret_key.pem"
CHAIN_NAME = os.getenv("CASPER_CHAIN_NAME", "casper-test")

# FIX #6: No hardcoded API key — read from environment variable
CASPER_API_KEY = os.getenv("CASPER_API_KEY", "")
RPC_URL = os.getenv("CASPER_NODE_URL", "https://node.testnet.casper.network/rpc")

RPC_HEADERS = {"Content-Type": "application/json"}
if CASPER_API_KEY:
    RPC_HEADERS["Authorization"] = CASPER_API_KEY

# Load contract hashes from transaction_hashes_live.json (not deploy_hashes_live.json)
HASHES_FILE = ROOT / "transaction_hashes_live.json"
if not HASHES_FILE.exists():
    # Fallback to transaction_hashes.json
    HASHES_FILE = ROOT / "transaction_hashes.json"

with open(HASHES_FILE) as f:
    CONTRACT_HASHES = json.load(f)

# ──────────────────────────────────────────────────────────────────────────
# FIX #1: 17 interaction calls with CORRECT entry points matching Rust code
# ──────────────────────────────────────────────────────────────────────────
#
# Entry point signatures from the actual Rust contracts:
#
#   AuditTrail:  record_finding(address: String, risk_type: String,
#                               severity: String, confidence: u8,
#                               description: String) -> u64
#
#   RiskOracle:  update_score(address: String, score: u8, risk_type: String,
#                             confidence: u8, block_height: u64, finding_id: u64)
#
#   SentinelAlertLog:  log_alert(subscriber_address: String, finding_id: u64,
#                                severity: String, risk_type: String,
#                                block_height: u64, timestamp: u64, delivered: bool)
#
#   AgentBehaviorIndex:  record_decision(agent_name: String, confidence: u8,
#                                        correction_applied: bool,
#                                        safety_rejected: bool, block_height: u64)
#
#   RiskPolicyManager:  update_policy(min_confidence_threshold: u8,
#                                     critical_score_threshold: u8,
#                                     high_score_threshold: u8,
#                                     medium_score_threshold: u8,
#                                     max_retry_count: u8,
#                                     safety_rejection_threshold: u8)
#
#   SentinelRegistry:  register(address: String, webhook_url: String,
#                               min_severity: String, timestamp: u64)
#
#   SentinelCredit:  deposit(account_address: String)  [payable]
#
#   SubscriberVault:  open_vault(subscriber_address: String,
#                                initial_deposit: U512, lock_blocks: u64,
#                                auto_renew: bool, monthly_spend_limit: U512,
#                                current_block: u64)  [payable]
# ──────────────────────────────────────────────────────────────────────────

try:
    import pycspr
    from pycspr.factory import create_deploy, create_deploy_parameters, parse_private_key
    from pycspr.types.crypto import KeyAlgorithm
    from pycspr.types.cl import CLV_U512, CLV_String, CLV_U64, CLV_U8, CLV_Bool
    from pycspr.types.node.rpc.complex import (
        DeployArgument,
        DeployOfModuleBytes,
        DeployOfStoredContractByHash,
    )
    _PYCSPR_AVAILABLE = True
except ImportError:
    _PYCSPR_AVAILABLE = False
    logger.warning("pycspr not available — will attempt httpx-only mode")


# ─── Interaction definitions ─────────────────────────────────────────────
# Each: (contract_name, entry_point, args_builder_func, description)

def build_interactions():
    """Build all 17 interactions with correct entry points."""
    interactions = []

    # ── AuditTrail — 3 calls: record_finding ────────────────────────────
    interactions.append((
        "AuditTrail",
        "record_finding",
        lambda: [
            DeployArgument("address", CLV_String("casper1proto_a")),
            DeployArgument("risk_type", CLV_String("whale_dump")),
            DeployArgument("severity", CLV_String("CRITICAL")),
            DeployArgument("confidence", CLV_U8(92)),
            DeployArgument("description", CLV_String("Whale wallet 0xabc dumped 22% of TVL in 1h")),
        ],
        "Record CRITICAL whale_dump finding",
    ))
    interactions.append((
        "AuditTrail",
        "record_finding",
        lambda: [
            DeployArgument("address", CLV_String("casper1proto_b")),
            DeployArgument("risk_type", CLV_String("depeg")),
            DeployArgument("severity", CLV_String("HIGH")),
            DeployArgument("confidence", CLV_U8(85)),
            DeployArgument("description", CLV_String("Stablecoin depeg detected — price dropped 4.2%")),
        ],
        "Record HIGH depeg finding",
    ))
    interactions.append((
        "AuditTrail",
        "record_finding",
        lambda: [
            DeployArgument("address", CLV_String("casper1proto_c")),
            DeployArgument("risk_type", CLV_String("wash_trade")),
            DeployArgument("severity", CLV_String("MEDIUM")),
            DeployArgument("confidence", CLV_U8(78)),
            DeployArgument("description", CLV_String("Suspicious repeat trades between linked wallets")),
        ],
        "Record MEDIUM wash_trade finding",
    ))

    # ── RiskOracle — 2 calls: update_score ──────────────────────────────
    interactions.append((
        "RiskOracle",
        "update_score",
        lambda: [
            DeployArgument("address", CLV_String("casper1proto_a")),
            DeployArgument("score", CLV_U8(87)),
            DeployArgument("risk_type", CLV_String("whale_concentration")),
            DeployArgument("confidence", CLV_U8(92)),
            DeployArgument("block_height", CLV_U64(1_500_000)),
            DeployArgument("finding_id", CLV_U64(0)),
        ],
        "Update risk score for proto_a — whale_concentration",
    ))
    interactions.append((
        "RiskOracle",
        "update_score",
        lambda: [
            DeployArgument("address", CLV_String("casper1proto_b")),
            DeployArgument("score", CLV_U8(42)),
            DeployArgument("risk_type", CLV_String("depeg")),
            DeployArgument("confidence", CLV_U8(85)),
            DeployArgument("block_height", CLV_U64(1_500_001)),
            DeployArgument("finding_id", CLV_U64(1)),
        ],
        "Update risk score for proto_b — depeg",
    ))

    # ── SentinelAlertLog — 3 calls: log_alert ───────────────────────────
    interactions.append((
        "SentinelAlertLog",
        "log_alert",
        lambda: [
            DeployArgument("subscriber_address", CLV_String("casper1sub1")),
            DeployArgument("finding_id", CLV_U64(0)),
            DeployArgument("severity", CLV_String("CRITICAL")),
            DeployArgument("risk_type", CLV_String("whale_dump")),
            DeployArgument("block_height", CLV_U64(1_500_000)),
            DeployArgument("timestamp", CLV_U64(1700000000000)),
            DeployArgument("delivered", CLV_Bool(True)),
        ],
        "Log CRITICAL alert to subscriber",
    ))
    interactions.append((
        "SentinelAlertLog",
        "log_alert",
        lambda: [
            DeployArgument("subscriber_address", CLV_String("casper1sub2")),
            DeployArgument("finding_id", CLV_U64(1)),
            DeployArgument("severity", CLV_String("HIGH")),
            DeployArgument("risk_type", CLV_String("depeg")),
            DeployArgument("block_height", CLV_U64(1_500_001)),
            DeployArgument("timestamp", CLV_U64(1700000001000)),
            DeployArgument("delivered", CLV_Bool(True)),
        ],
        "Log HIGH alert to subscriber",
    ))
    interactions.append((
        "SentinelAlertLog",
        "log_alert",
        lambda: [
            DeployArgument("subscriber_address", CLV_String("casper1sub3")),
            DeployArgument("finding_id", CLV_U64(2)),
            DeployArgument("severity", CLV_String("MEDIUM")),
            DeployArgument("risk_type", CLV_String("wash_trade")),
            DeployArgument("block_height", CLV_U64(1_500_002)),
            DeployArgument("timestamp", CLV_U64(1700000002000)),
            DeployArgument("delivered", CLV_Bool(False)),
        ],
        "Log MEDIUM alert (delivery pending)",
    ))

    # ── AgentBehaviorIndex — 2 calls: record_decision ───────────────────
    interactions.append((
        "AgentBehaviorIndex",
        "record_decision",
        lambda: [
            DeployArgument("agent_name", CLV_String("AnomalyAgent")),
            DeployArgument("confidence", CLV_U8(91)),
            DeployArgument("correction_applied", CLV_Bool(False)),
            DeployArgument("safety_rejected", CLV_Bool(False)),
            DeployArgument("block_height", CLV_U64(1_500_000)),
        ],
        "Record AnomalyAgent decision (high confidence)",
    ))
    interactions.append((
        "AgentBehaviorIndex",
        "record_decision",
        lambda: [
            DeployArgument("agent_name", CLV_String("SelfCorrectionAgent")),
            DeployArgument("confidence", CLV_U8(52)),
            DeployArgument("correction_applied", CLV_Bool(True)),
            DeployArgument("safety_rejected", CLV_Bool(False)),
            DeployArgument("block_height", CLV_U64(1_500_001)),
        ],
        "Record SelfCorrectionAgent decision (low confidence, corrected)",
    ))

    # ── RiskPolicyManager — 2 calls: update_policy ──────────────────────
    interactions.append((
        "RiskPolicyManager",
        "update_policy",
        lambda: [
            DeployArgument("min_confidence_threshold", CLV_U8(80)),
            DeployArgument("critical_score_threshold", CLV_U8(75)),
            DeployArgument("high_score_threshold", CLV_U8(55)),
            DeployArgument("medium_score_threshold", CLV_U8(35)),
            DeployArgument("max_retry_count", CLV_U8(3)),
            DeployArgument("safety_rejection_threshold", CLV_U8(85)),
        ],
        "Update risk policy — tighter thresholds v2",
    ))
    interactions.append((
        "RiskPolicyManager",
        "update_policy",
        lambda: [
            DeployArgument("min_confidence_threshold", CLV_U8(78)),
            DeployArgument("critical_score_threshold", CLV_U8(78)),
            DeployArgument("high_score_threshold", CLV_U8(58)),
            DeployArgument("medium_score_threshold", CLV_U8(38)),
            DeployArgument("max_retry_count", CLV_U8(2)),
            DeployArgument("safety_rejection_threshold", CLV_U8(82)),
        ],
        "Update risk policy — adjusted thresholds v3",
    ))

    # ── SentinelRegistry — 2 calls: register ────────────────────────────
    interactions.append((
        "SentinelRegistry",
        "register",
        lambda: [
            DeployArgument("address", CLV_String("casper1sub1")),
            DeployArgument("webhook_url", CLV_String("https://api.vaultwatch.io/v2/hooks/sub1")),
            DeployArgument("min_severity", CLV_String("CRITICAL")),
            DeployArgument("timestamp", CLV_U64(1700000000000)),
        ],
        "Register subscriber for CRITICAL+ alerts",
    ))
    interactions.append((
        "SentinelRegistry",
        "register",
        lambda: [
            DeployArgument("address", CLV_String("casper1sub2")),
            DeployArgument("webhook_url", CLV_String("https://mcp.vaultwatch.io/v2/hooks/sub2")),
            DeployArgument("min_severity", CLV_String("HIGH")),
            DeployArgument("timestamp", CLV_U64(1700000001000)),
        ],
        "Register subscriber for HIGH+ alerts",
    ))

    # ── SentinelCredit — 1 call: deposit (payable) ──────────────────────
    interactions.append((
        "SentinelCredit",
        "deposit",
        lambda: [
            DeployArgument("account_address", CLV_String("casper1sub1")),
        ],
        "Deposit CSPR credits (payable entry point)",
    ))

    # ── SubscriberVault — 1 call: open_vault (payable) ──────────────────
    interactions.append((
        "SubscriberVault",
        "open_vault",
        lambda: [
            DeployArgument("subscriber_address", CLV_String("casper1sub1")),
            DeployArgument("initial_deposit", CLV_U512(100_000_000_000)),  # 100 CSPR in motes
            DeployArgument("lock_blocks", CLV_U64(0)),  # no lock
            DeployArgument("auto_renew", CLV_Bool(True)),
            DeployArgument("monthly_spend_limit", CLV_U512(500_000_000_000)),
            DeployArgument("current_block", CLV_U64(1_500_000)),
        ],
        "Open vault with initial CSPR deposit (payable entry point)",
    ))

    return interactions


# ─── RPC helpers ─────────────────────────────────────────────────────────

def rpc_call(method: str, params: dict, timeout: int = 30) -> dict:
    """Make a Casper JSON-RPC call via httpx (no hardcoded auth)."""
    payload = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(RPC_URL, json=payload, headers=RPC_HEADERS)
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data.get("result", {})
    except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
        logger.warning("RPC call failed: %s", exc)
        return {}


def put_deploy(deploy) -> str:
    """Submit a signed deploy to the network."""
    encoded = pycspr.serializer.to_json(deploy)
    result = rpc_call("account_put_deploy", {"deploy": encoded})
    deploy_hash = result.get("deploy_hash")
    if not deploy_hash:
        raise RuntimeError("No deploy_hash returned from account_put_deploy")
    return deploy_hash


def verify_deploy(deploy_hash: str, timeout: int = 120, poll_interval: int = 5) -> dict:
    """Poll until a deploy is executed and return the execution result."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = rpc_call("info_get_deploy", {"deploy_hash": deploy_hash})
        exec_results = result.get("execution_results", [])
        if exec_results:
            for er in exec_results:
                outcome = er.get("result", {})
                if "Success" in outcome:
                    return {"status": "success", "details": outcome["Success"]}
                elif "Failure" in outcome:
                    return {"status": "failure", "details": outcome["Failure"]}
        time.sleep(poll_interval)

    return {"status": "timeout", "details": f"Deploy {deploy_hash} not confirmed within {timeout}s"}


def make_payment(amount_motes: int) -> DeployOfModuleBytes:
    """Standard Casper payment module bytes."""
    return DeployOfModuleBytes(
        module_bytes=b"",
        args=[DeployArgument("amount", CLV_U512(amount_motes))],
    )


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    if not _PYCSPR_AVAILABLE:
        logger.error("pycspr is required for broadcast_interactions. Install with: pip install pycspr")
        sys.exit(1)

    if not KEY_PATH.exists():
        logger.error("secret_key.pem not found at %s", KEY_PATH)
        sys.exit(1)

    key = parse_private_key(KEY_PATH, KeyAlgorithm.SECP256K1)
    logger.info("Key loaded. Pubkey: %s...", key.to_public_key().account_key.hex()[:20])

    interactions = build_interactions()
    logger.info("Prepared %d interactions with correct entry points", len(interactions))

    results = []
    verified_count = 0

    for i, (contract_name, entry_point, args_builder, description) in enumerate(interactions, 1):
        contract_hash_hex = CONTRACT_HASHES.get(contract_name)
        if not contract_hash_hex:
            logger.error("[%d/%d] %s: contract hash not found", i, len(interactions), contract_name)
            results.append({
                "contract": contract_name,
                "entry_point": entry_point,
                "deploy_hash": None,
                "error": "Contract hash not found in transaction_hashes_live.json",
                "status": "failed",
                "verified": False,
            })
            continue

        logger.info("[%d/%d] %s::%s — %s", i, len(interactions), contract_name, entry_point, description)

        try:
            cl_args = args_builder()

            # For payable entry points, attach CSPR value
            payment_amount = 5_000_000_000  # 5 CSPR for gas
            attached_value = 0
            if entry_point in ("deposit", "open_vault", "top_up"):
                attached_value = 10_000_000_000  # 10 CSPR attached for payable methods
                payment_amount = 5_000_000_000

            params = create_deploy_parameters(account=key, chain_name=CHAIN_NAME)
            payment = make_payment(payment_amount)

            session = DeployOfStoredContractByHash(
                hash=bytes.fromhex(contract_hash_hex),
                entry_point=entry_point,
                args=cl_args,
            )
            deploy = create_deploy(params, payment, session)
            deploy.approve(key)

            deploy_hash = put_deploy(deploy)
            logger.info("  -> Deploy hash: %s", deploy_hash)

            # Verify execution
            logger.info("  -> Verifying execution...")
            verification = verify_deploy(deploy_hash, timeout=60)
            is_verified = verification["status"] == "success"

            if is_verified:
                verified_count += 1
                logger.info("  -> [VERIFIED ✓] Execution successful")
            else:
                logger.warning("  -> [UNVERIFIED] %s", verification.get("details", "unknown"))

            results.append({
                "contract": contract_name,
                "entry_point": entry_point,
                "deploy_hash": deploy_hash,
                "link": f"https://testnet.cspr.live/deploy/{deploy_hash}",
                "description": description,
                "status": "submitted",
                "verified": is_verified,
                "verification_details": verification.get("details", ""),
            })

        except Exception as exc:
            logger.error("  FAILED: %s", exc)
            results.append({
                "contract": contract_name,
                "entry_point": entry_point,
                "deploy_hash": None,
                "error": str(exc),
                "status": "failed",
                "verified": False,
            })

        time.sleep(2)  # avoid nonce conflicts

    # ─── Save interaction results ────────────────────────────────────────
    out_path = ROOT / "proof" / "interaction_hashes.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", out_path)

    # ─── Update PROOF.md with verified markers ──────────────────────────
    proof_md_path = ROOT / "proof" / "PROOF.md"
    proof_section = _build_proof_section(results, verified_count)
    _append_to_proof_md(proof_md_path, proof_section)

    # ─── Summary ─────────────────────────────────────────────────────────
    successful = [r for r in results if r.get("deploy_hash")]
    failed = [r for r in results if r.get("status") == "failed"]
    total_hashes = 8 + len(successful)

    logger.info("\n=== INTERACTION SUMMARY ===")
    logger.info("Submitted: %d/%d", len(successful), len(results))
    logger.info("Verified:  %d/%d", verified_count, len(results))
    logger.info("Failed:    %d", len(failed))
    logger.info("Total TX hashes (8 deploy + %d interaction): %d", len(successful), total_hashes)

    print("\n=== SUBMITTED INTERACTION TX HASHES ===")
    for r in successful:
        verified_marker = "✓" if r.get("verified") else "?"
        print(f"  [{verified_marker}] {r['contract']:25s} {r['entry_point']:25s} {r['deploy_hash']}")

    print(f"\nTotal on-chain TX hashes: {total_hashes}")
    if total_hashes >= 25:
        print("Blueprint requirement: 25+ hashes ✓")

    return successful


def _build_proof_section(results: list, verified_count: int) -> str:
    """Build a PROOF.md section with verified markers."""
    lines = [
        "\n---\n",
        "## Broadcast Interactions (Fix #1 — Correct Entry Points)\n",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n",
        f"**Verified**: {verified_count}/{len(results)} deploys confirmed on-chain\n",
        "",
        "| # | Contract | Entry Point | Deploy Hash | Verified |",
        "|---|----------|-------------|-------------|----------|",
    ]

    for i, r in enumerate(results, 1):
        contract = r.get("contract", "?")
        ep = r.get("entry_point", "?")
        dh = r.get("deploy_hash", "N/A")
        if dh and len(dh) > 16:
            dh = dh[:16] + "..."
        verified = "✓" if r.get("verified") else "✗"
        lines.append(f"| {i} | {contract} | {ep} | `{dh}` | {verified} |")

    lines.append("")
    return "\n".join(lines)


def _append_to_proof_md(proof_path: Path, section: str) -> None:
    """Append the interaction proof section to PROOF.md."""
    try:
        if proof_path.exists():
            with open(proof_path) as f:
                existing = f.read()
        else:
            existing = "# VaultWatch — Proof of On-Chain Activity\n"

        with open(proof_path, "w") as f:
            f.write(existing + section)

        logger.info("PROOF.md updated at %s", proof_path)
    except Exception as exc:
        logger.warning("Could not update PROOF.md: %s", exc)


if __name__ == "__main__":
    main()
