"""Pytest configuration + shared fixtures for the VaultWatch E2E test suite.

The E2E suite runs against the **real Casper Testnet** (`casper-test`):

  * All reads use ``query_global_state`` / ``state_get_account_info`` /
    ``info_get_status`` JSON-RPC calls (free, no gas).
  * All writes shell out to ``scripts/casper_call.cjs`` (casper-js-sdk v5
    ``ContractCallBuilder`` + ``PrivateKey.fromPem``) and submit REAL
    deploys that consume REAL CSPR gas.

Because each write deploy consumes gas (~0.5 CSPR each, 5 CSPR payment),
the suite is OPT-IN: pass ``--run-e2e`` to enable it. By default it is
SKIPPED so a normal ``pytest tests/`` run does NOT touch the network.

CSPR.click AI Agent Skill integration (Task CSPRCLICK-1)
--------------------------------------------------------
The suite now uses the :class:`vaultwatch.agents.agent_wallet.AgentWallet`
abstraction for wallet creation + signing, replacing the prior "manual key
management" flow (where a hardcoded ``secret_key.pem`` was required at the
repo root).

The new flow:
  1. If ``$VAULTWATCH_AGENT_KEY_PATH`` is set (or ``--e2e-signer-pem`` is
     passed), the suite LOADS that key as the agent wallet. This is the
     backward-compat path — the existing funded Account-2 key continues to
     work when ``VAULTWATCH_AGENT_KEY_PATH`` points at it.
  2. Otherwise, the suite auto-creates a NEW agent wallet at
     ``~/.vaultwatch/agent_key.pem`` via ``PrivateKey.generate()`` and
     prints the public key + faucet URL. The user funds it once via the
     testnet faucet, then re-runs the suite.

Required environment
--------------------
* One of:
    - ``$VAULTWATCH_AGENT_KEY_PATH`` pointing at a funded agent key PEM, OR
    - ``secret_key.pem`` at the repo root (legacy, funded Account-2 key), OR
    - nothing (the suite auto-creates a new wallet + prints the faucet URL)
* ``node.testnet.casper.network`` reachable (HTTPS POST JSON-RPC 2.0).

Optional env
------------
* ``CASPER_RPC_URL`` — override RPC endpoint (default: public testnet node).
* ``VAULTWATCH_SIGNER_ALGO`` — override key algorithm (default: secp256k1).
* ``VAULTWATCH_E2E_MIN_BALANCE_CSPR`` — minimum balance floor; suite aborts
  below this to avoid burning the deployer key dry (default: 100).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pytest

if TYPE_CHECKING:
    from agents.agent_wallet import AgentWallet

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Constants — verified on-chain as of 2026-07-21 (proof/PROOF.md §1)
# ---------------------------------------------------------------------------

#: Public Casper testnet RPC endpoint (no API key required).
DEFAULT_RPC_URL = "https://node.testnet.casper.network/rpc"

#: Casper testnet chain identifier.
CHAIN_NAME = "casper-test"

#: Default gas payment per deploy (5 CSPR = 5_000_000_000 motes). Same value
#: used by scripts/broadcast_interactions.py for the 21 verified interactions.
DEFAULT_PAYMENT_MOTES = 5_000_000_000

#: Default verify timeout — how long to poll info_get_deploy before giving up.
#: Casper testnet block time is ~16s; deploys typically commit within 1-3
#: blocks. 120s is generous; 240s is the absolute max for heavy payable
#: deploys.
DEFAULT_VERIFY_TIMEOUT_MS = 120_000

#: Account 2 — funded deployer; owns the v1 AuditTrail/RiskOracle/etc. packages.
DEPLOYER_PUBLIC_KEY = "02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db"
DEPLOYER_ACCOUNT_HASH = "account-hash-0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68"

#: Default deployer secret key path (Account 2).
DEFAULT_SIGNER_PEM = ROOT / "secret_key.pem"

#: v1 contract hashes (deployed 2026-07-11, verified-success).
#: Source: deploy_hashes_live.json.
CONTRACT_HASHES: Dict[str, str] = {
    "AuditTrail": "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
    "RiskOracle": "234a34a71fb04625971373b06b73ac6dbc5f7d701f7e96621c752d73ccde80ff",
    "SentinelCredit": "993d8947a6c8220539efaea87c7631c9fc45780c674406d48487bcf66fb1cbfb",
    "SentinelRegistry": "9cce03a0e5d1aa3dab07da50afb4cb9eaba29973eb2b1e766cc6724a1e34e31e",
    "SentinelAlertLog": "43f9b7df3f9f808db8b035c13ae0bac0b47335709abeafdc36e6a9bffe9b9322",
    "AgentBehaviorIndex": "1a976fe839366c4399541055245695cf94626b3d99c0f3a6675ae761395d822b",
    "RiskPolicyManager": "1027cb2a989b75d8b29b82cab60a8b12a892138a5704cdd4753a0862f65b1d85",
    "SubscriberVault": "9a93db9c1f315f1ed34ee55e46f65ed28585f9529fb8427aedf937a6ea0d7bd0",
}

#: Contract package hashes (verified on-chain via query_global_state).
CONTRACT_PACKAGE_HASHES: Dict[str, str] = {
    "AuditTrail": "hash-7e653fc142ddd4f1759aec0c2f4fb0537eb167cfb9771d12c37ae55f29c270fa",
    "RiskOracle": "hash-1a47fd766eb021aa83cc44b5a729920842253510936cbe9a1545bf6dc7c2e974",
    "SentinelCredit": "hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae",
    "SentinelRegistry": "hash-d97d1f1ef30bf765fbf13aa11817fea409b67056dd59faf6de28c94ad85a5f82",
    "SentinelAlertLog": "hash-f75ce1bc111d185c39d7c81d5a18b093749643957b8c3ba3309613401fb14b78",
    "AgentBehaviorIndex": "hash-d888dc3696046633582f1355f9708dfbd5acde3528466a562fa0601ad6eacbd2",
    "RiskPolicyManager": "hash-aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4",
    "SubscriberVault": "hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211",
}

#: Initial install deploy hashes — loaded from transaction_hashes_live.json
#: (the canonical source). On Casper testnet, deploys are pruned after ~7 days,
#: so the July 11 installs may no longer resolve via info_get_deploy. The
#: contracts themselves remain queryable via query_global_state (proven in
#: test_contracts_on_chain.py). The historical-deploys test handles pruning
#: gracefully — see test_historical_deploys.py.
def _load_install_hashes() -> Dict[str, str]:
    p = ROOT / "transaction_hashes_live.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


INSTALL_DEPLOY_HASHES: Dict[str, str] = _load_install_hashes()


#: Historical interaction deploy hashes (21 deploys, verified-success on
#: 2026-07-21 — loaded from proof/interaction_hashes.json, the canonical
#: source). Loaded at import time to avoid transcription errors.
def _load_interaction_hashes() -> Tuple[str, ...]:
    p = ROOT / "proof" / "interaction_hashes.json"
    if p.exists():
        with open(p) as f:
            data = json.load(f)
        return tuple(d["deploy_hash"] for d in data)
    return ()


HISTORICAL_INTERACTION_HASHES: Tuple[str, ...] = _load_interaction_hashes()


#: Upgrade-lifecycle deploy hashes (6 deploys from PROOF.md §10.1, loaded
#: from proof/upgrade_hashes.json).
def _load_upgrade_hashes() -> Tuple[str, ...]:
    p = ROOT / "proof" / "upgrade_hashes.json"
    if p.exists():
        with open(p) as f:
            data = json.load(f)
        # The JSON shape: {"deploys": {"<step_name>": {"deploy_hash": ...}, ...}}
        # OR {"deploys": [{"deploy_hash": ...}, ...]}
        # OR a list of {"deploy_hash": ...}. Handle all.
        if isinstance(data, dict) and "deploys" in data:
            deploys = data["deploys"]
            if isinstance(deploys, dict):
                return tuple(v["deploy_hash"] for v in deploys.values() if "deploy_hash" in v)
            if isinstance(deploys, list):
                return tuple(d["deploy_hash"] for d in deploys if "deploy_hash" in d)
        if isinstance(data, list):
            return tuple(d["deploy_hash"] for d in data if "deploy_hash" in d)
    return ()


UPGRADE_DEPLOY_HASHES: Tuple[str, ...] = _load_upgrade_hashes()

#: Explorer URL prefix for human-friendly deploy links.
EXPLORER_URL = "https://testnet.cspr.live/deploy/"


# ---------------------------------------------------------------------------
# pytest hook: --run-e2e opt-in flag
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--run-e2e`` CLI flag."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests against the REAL Casper testnet (consumes CSPR gas).",
    )
    parser.addoption(
        "--e2e-rpc-url",
        default=os.getenv("CASPER_RPC_URL", DEFAULT_RPC_URL),
        help=f"Casper RPC URL (default: {DEFAULT_RPC_URL})",
    )
    parser.addoption(
        "--e2e-signer-pem",
        default=str(DEFAULT_SIGNER_PEM),
        help=f"Path to deployer secret key PEM (default: {DEFAULT_SIGNER_PEM})",
    )
    parser.addoption(
        "--e2e-min-balance-cspr",
        type=int,
        default=int(os.getenv("VAULTWATCH_E2E_MIN_BALANCE_CSPR", "100")),
        help="Minimum deployer balance (CSPR) required to run the suite (default: 100).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """Skip e2e tests unless --run-e2e was passed."""
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(
        reason="E2E suite is opt-in — pass --run-e2e to run against the live Casper testnet "
        "(each write deploy consumes real CSPR gas).",
    )
    for item in items:
        if "e2e" in item.keywords or "/tests/e2e/" in str(item.fspath):
            item.add_marker(skip_e2e)


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``e2e`` marker."""
    config.addinivalue_line(
        "markers",
        "e2e: marks tests as end-to-end (real Casper testnet; opt-in via --run-e2e)",
    )


# ---------------------------------------------------------------------------
# Low-level RPC helper (sync, urllib — no extra deps)
# ---------------------------------------------------------------------------


def rpc_call(rpc_url: str, method: str, params: Any) -> Dict[str, Any]:
    """Make a JSON-RPC 2.0 POST call and return the ``result`` field.

    Raises ``RuntimeError`` if the RPC returns an ``error`` or a non-200 HTTP
    status, so test failures point at the underlying RPC problem (not a
    confusing KeyError downstream).
    """
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    req = urllib.request.Request(
        rpc_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"RPC {method} network error: {exc}") from exc
    if "error" in data:
        raise RuntimeError(f"RPC {method} error: {json.dumps(data['error'])}")
    return data.get("result", {})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rpc_url(request: pytest.FixtureRequest) -> str:
    """The Casper testnet RPC URL for the session."""
    return request.config.getoption("--e2e-rpc-url")


@pytest.fixture(scope="session")
def signer_pem(request: pytest.FixtureRequest) -> str:
    """Path to the deployer secret key PEM file (asserts the file exists).

    CSPR.click AI Agent Skill integration: this fixture now resolves the
    agent wallet key path via (in priority order):
      1. ``--e2e-signer-pem`` CLI option
      2. ``$VAULTWATCH_AGENT_KEY_PATH`` env var
      3. ``$HOME/.vaultwatch/agent_key.pem`` (auto-created on first run)
      4. ``<repo-root>/secret_key.pem`` (legacy fallback for Account-2)

    If none exist, a NEW agent wallet is programmatically created at the
    default path and the faucet URL is printed. The wallet must then be
    funded manually before re-running the suite.
    """
    pem = request.config.getoption("--e2e-signer-pem")
    if pem and os.path.exists(pem):
        return pem
    # Try env var
    env_pem = os.getenv("VAULTWATCH_AGENT_KEY_PATH")
    if env_pem and os.path.exists(env_pem):
        return env_pem
    # Try default agent wallet path
    default_pem = os.path.expanduser("~/.vaultwatch/agent_key.pem")
    if os.path.exists(default_pem):
        return default_pem
    # Legacy fallback — repo-root secret_key.pem (Account-2)
    legacy_pem = str(ROOT / "secret_key.pem")
    if os.path.exists(legacy_pem):
        return legacy_pem
    # No key found — auto-create a new agent wallet via the Node helper
    helper = ROOT / "scripts" / "csprclick_agent_wallet.cjs"
    if helper.exists():
        import subprocess
        proc = subprocess.run(
            ["node", str(helper), "create"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            info = json.loads(proc.stdout)
            print(
                "\n[CSPR.click AI Agent Skill] Created NEW agent wallet:\n"
                f"  public_key: {info.get('public_key')}\n"
                f"  account_hash: {info.get('account_hash')}\n"
                f"  key_path: {info.get('key_path')}\n"
                f"  Faucet: {info.get('faucet_url')} (paste the public key above)\n"
                f"  Explorer: {info.get('explorer_url')}\n"
                "Fund the wallet, then re-run with --run-e2e.\n"
            )
        pytest.skip(
            "Auto-created a NEW agent wallet — fund it at the faucet URL "
            "above, then re-run with --run-e2e."
        )
    assert False, (
        "Deployer secret key not found. Place the Account-2 PEM at "
        "vaultwatch/secret_key.pem, OR set VAULTWATCH_AGENT_KEY_PATH, OR "
        "run `node scripts/csprclick_agent_wallet.cjs create` to auto-create."
    )


@pytest.fixture(scope="session")
def agent_wallet(signer_pem: str, rpc_url: str) -> "AgentWallet":
    """Session-scoped :class:`AgentWallet` instance — the CSPR.click AI Agent
    Skill abstraction over the deployer key.

    Replaces direct PEM-path manipulation throughout the e2e suite. The
    wallet is loaded from the same path as :func:`signer_pem` (which
    auto-discovers or auto-creates the agent key per the priority order
    documented above).
    """
    from agents.agent_wallet import AgentWallet  # local import to avoid SDK dep at module load

    return AgentWallet.load(key_path=Path(signer_pem), rpc_url=rpc_url)


@pytest.fixture(scope="session")
def casper_node_status(rpc_url: str) -> Dict[str, Any]:
    """Session-scoped: ``info_get_status`` result (chain name + api_version)."""
    result = rpc_call(rpc_url, "info_get_status", {})
    assert result, "info_get_status returned empty result"
    assert result.get("chainspec_name") == CHAIN_NAME, (
        f"wrong chain: expected {CHAIN_NAME!r}, got {result.get('chainspec_name')!r}"
    )
    return result


@pytest.fixture(scope="session")
def state_root_hash(rpc_url: str) -> str:
    """Session-scoped: latest chain state root hash (for state reads)."""
    result = rpc_call(rpc_url, "chain_get_state_root_hash", {})
    srh = result.get("state_root_hash")
    assert srh and len(srh) == 64, f"bad state root hash: {srh!r}"
    return srh


@pytest.fixture(scope="session")
def deployer_account(rpc_url: str, state_root_hash: str) -> Dict[str, Any]:
    """Session-scoped: deployer account record (named_keys, balance, etc.)."""
    result = rpc_call(
        rpc_url,
        "state_get_account_info",
        {"public_key": DEPLOYER_PUBLIC_KEY},
    )
    account = result.get("account")
    assert account, f"deployer account not found on testnet: {result}"
    # Read main_purse balance for the gas-floor assertion.
    purse = account.get("main_purse", "")
    assert purse, "deployer has no main_purse"
    bal_result = rpc_call(
        rpc_url,
        "state_get_balance",
        {"state_root_hash": state_root_hash, "purse_uref": purse},
    )
    account["_main_purse_balance_motes"] = int(bal_result.get("balance_value", 0))
    return account


@pytest.fixture(scope="session")
def deployer_balance_cspr(deployer_account: Dict[str, Any]) -> int:
    """Session-scoped: deployer balance in whole CSPR (integer division)."""
    motes = deployer_account["_main_purse_balance_motes"]
    return motes // 1_000_000_000


# ---------------------------------------------------------------------------
# Helper: submit a real stored-contract deploy via scripts/casper_call.cjs
# ---------------------------------------------------------------------------


def submit_real_deploy(
    *,
    contract_name: Optional[str] = None,
    contract_hash: Optional[str] = None,
    entry_point: str,
    args: Dict[str, Dict[str, str]],
    rpc_url: str,
    signer_pem: str,
    payment_motes: int = DEFAULT_PAYMENT_MOTES,
    verify_timeout_ms: int = DEFAULT_VERIFY_TIMEOUT_MS,
) -> Dict[str, Any]:
    """Submit + verify a REAL stored-contract deploy on Casper testnet.

    Shells out to ``scripts/casper_call.cjs`` (casper-js-sdk v5). The helper
    builds the deploy via ``ContractCallBuilder``, signs with the deployer
    ``PrivateKey.fromPem``, submits via ``account_put_deploy``, and verifies
    via ``info_get_deploy`` (Casper 2.x ``Version2.error_message == None`` =
    success). Returns the helper's JSON response.

    Args:
        contract_name: key into ``CONTRACT_HASHES`` (e.g. ``"AuditTrail"``).
            Mutually exclusive with ``contract_hash``; one MUST be provided.
        contract_hash: raw 64-hex contract hash (no ``hash-`` prefix). Use
            this to call a non-default contract version (e.g. the v2
            RiskPolicyManager on Account-2's fresh package).
        entry_point: on-chain entry point name.
        args: typed args dict — ``{name: {"type": "string|bool|u8|u64|u512",
            "value": "..."}}``. ``int`` values must be passed as ``str``.
        rpc_url: JSON-RPC endpoint.
        signer_pem: path to the deployer secret key PEM.
        payment_motes: gas payment in motes (default 5 CSPR).
        verify_timeout_ms: how long to poll for the deploy to be committed.

    Returns:
        Dict with ``success``, ``deploy_hash``, ``block_hash``, ``cost_motes``,
        ``link``, ``deployer_account_hash``, ``error`` fields.
    """
    import subprocess

    helper = ROOT / "scripts" / "casper_call.cjs"
    assert helper.exists(), f"casper_call.cjs not found at {helper}"

    if contract_hash is None:
        assert contract_name is not None, "must provide contract_name or contract_hash"
        contract_hash = CONTRACT_HASHES[contract_name]
    else:
        # Strip 'hash-' prefix if the caller passed it.
        contract_hash = contract_hash.replace("hash-", "")
        assert len(contract_hash) == 64, f"bad contract_hash length: {contract_hash!r}"

    payload = {
        "contract_hash": contract_hash,
        "entry_point": entry_point,
        "args": args,
        "payment_motes": payment_motes,
        "signer_pem_path": signer_pem,
        "rpc_url": rpc_url,
        "key_algorithm": os.getenv("VAULTWATCH_SIGNER_ALGO", "secp256k1"),
        "verify_timeout_ms": verify_timeout_ms,
    }

    proc = subprocess.run(
        ["node", str(helper)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(ROOT),
        timeout=verify_timeout_ms // 1000 + 60,  # generous subprocess timeout
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"casper_call.cjs exited {proc.returncode} for "
            f"{contract_name or contract_hash[:8]}::{entry_point}: {stderr}"
        )
    result = json.loads(proc.stdout.decode("utf-8"))
    return result


def verify_deploy_success(rpc_url: str, deploy_hash: str) -> Dict[str, Any]:
    """Fetch a deploy via ``info_get_deploy`` and assert its execution succeeded.

    Returns the ``execution_info.execution_result.Version2`` dict on success.
    Raises ``AssertionError`` if the deploy is not found or its execution
    result has a non-null ``error_message``.

    NOTE: Casper testnet prunes deploy history after ~7 days. For deploys
    older than that, use ``verify_deploy_exists_or_pruned`` (returns None
    for pruned deploys instead of raising).
    """
    result = rpc_call(rpc_url, "info_get_deploy", {"deploy_hash": deploy_hash})
    exec_info = result.get("execution_info", {})
    exec_result = exec_info.get("execution_result", {})
    v2 = exec_result.get("Version2")
    assert v2 is not None, (
        f"deploy {deploy_hash} has no Version2 execution result (Casper 1.x format?) — "
        f"raw: {json.dumps(exec_result)[:500]}"
    )
    assert v2.get("error_message") is None, (
        f"deploy {deploy_hash} FAILED on-chain: {v2.get('error_message')}"
    )
    return v2


def verify_deploy_exists_or_pruned(rpc_url: str, deploy_hash: str) -> Optional[Dict[str, Any]]:
    """Like ``verify_deploy_success``, but returns ``None`` for pruned deploys
    instead of raising.

    Casper testnet prunes deploy history after ~7 days. For deploys older
    than that, ``info_get_deploy`` returns RPC error code -32000 "No such
    deploy". This helper catches that specific error and returns None — the
    deploy may have existed historically (PROOF.md §1) but is no longer
    queryable. The contract state installed by the deploy is still
    verifiable via ``query_global_state`` (see test_contracts_on_chain.py).
    """
    try:
        result = rpc_call(rpc_url, "info_get_deploy", {"deploy_hash": deploy_hash})
    except RuntimeError as exc:
        msg = str(exc)
        # "No such deploy" / "no deploy for hash" = pruned. Anything else
        # (network error, malformed hash) = real failure.
        if "No such deploy" in msg or "no deploy for hash" in msg:
            return None
        raise
    exec_info = result.get("execution_info", {})
    exec_result = exec_info.get("execution_result", {})
    v2 = exec_result.get("Version2")
    if v2 is None:
        # Could be Casper 1.x format (Success/Failure) — try that too.
        if "Success" in exec_result:
            return exec_result["Success"]
        # Genuinely malformed — surface it.
        raise AssertionError(
            f"deploy {deploy_hash} has no Version2 execution result — "
            f"raw: {json.dumps(exec_result)[:500]}"
        )
    if v2.get("error_message") is not None:
        raise AssertionError(
            f"deploy {deploy_hash} FAILED on-chain: {v2.get('error_message')}"
        )
    return v2


def query_contract(rpc_url: str, contract_hash: str) -> Dict[str, Any]:
    """Query a contract's stored_value via ``query_global_state``."""
    result = rpc_call(
        rpc_url,
        "query_global_state",
        {"state_identifier": None, "key": f"hash-{contract_hash}"},
    )
    contract = result.get("stored_value", {}).get("Contract")
    assert contract, f"no Contract stored_value at hash-{contract_hash}: {result}"
    return contract


def query_contract_package(rpc_url: str, package_hash: str) -> Dict[str, Any]:
    """Query a contract package's stored_value via ``query_global_state``.

    ``package_hash`` may be either ``hash-<hex>`` (Casper 1.x format) or
    ``contract-package-<hex>`` (Casper 2.x format). Both work — Casper 2.x
    accepts either prefix.
    """
    result = rpc_call(
        rpc_url,
        "query_global_state",
        {"state_identifier": None, "key": package_hash},
    )
    pkg = result.get("stored_value", {}).get("ContractPackage")
    assert pkg, f"no ContractPackage stored_value at {package_hash}: {result}"
    return pkg


def normalize_package_hash(h: str) -> str:
    """Strip the ``hash-`` or ``contract-package-`` prefix from a package hash,
    returning the raw 64-char hex."""
    for prefix in ("hash-", "contract-package-"):
        if h.startswith(prefix):
            return h[len(prefix):]
    return h


# ---------------------------------------------------------------------------
# pytest fixtures that wrap the helpers above (for clean test usage)
# ---------------------------------------------------------------------------


@pytest.fixture
def submit_deploy(rpc_url: str, signer_pem: str, deployer_balance_cspr: int, request: pytest.FixtureRequest):
    """Function-scoped deploy helper with a session-scoped gas floor check.

    Asserts the deployer balance is above the floor before each deploy, so a
    mid-suite drain doesn't silently produce confusing failures.
    """
    floor = request.config.getoption("--e2e-min-balance-cspr")
    assert deployer_balance_cspr >= floor, (
        f"deployer balance {deployer_balance_cspr} CSPR is below the e2e floor of "
        f"{floor} CSPR — refusing to submit more deploys. Refill at "
        f"https://testnet.cspr.live/tools/faucet."
    )

    def _submit(
        contract_name: Optional[str] = None,
        entry_point: str = "",
        args: Optional[Dict[str, Dict[str, str]]] = None,
        payment_motes: int = DEFAULT_PAYMENT_MOTES,
        *,
        contract_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        return submit_real_deploy(
            contract_name=contract_name,
            contract_hash=contract_hash,
            entry_point=entry_point,
            args=args or {},
            rpc_url=rpc_url,
            signer_pem=signer_pem,
            payment_motes=payment_motes,
        )

    return _submit


@pytest.fixture
def verify_success(rpc_url: str):
    """Function-scoped wrapper around ``verify_deploy_success``."""
    return lambda deploy_hash: verify_deploy_success(rpc_url, deploy_hash)


@pytest.fixture
def query(rpc_url: str):
    """Function-scoped wrapper around ``query_contract``."""
    return lambda contract_name_or_hash: query_contract(
        rpc_url,
        contract_name_or_hash if len(contract_name_or_hash) == 64 and
        not contract_name_or_hash.startswith("hash-")
        else CONTRACT_HASHES.get(contract_name_or_hash, contract_name_or_hash.replace("hash-", "")),
    )


# ---------------------------------------------------------------------------
# Shared constants for tests
# ---------------------------------------------------------------------------

#: Unique salt injected into e2e deploy args so re-runs don't collide with
#: prior runs' on-chain state (e.g. register() of an already-registered
#: address would still succeed — but we want fresh observable state).
E2E_RUN_ID = str(int(time.time()))


def _e2e_address(suffix: str = "") -> str:
    """Build a unique e2e test address string.

    ``register`` deduplicates on the ``address`` arg, so re-runs of the suite
    on the same address would no-op semantically (the contract just overwrites
    the subscriber record). Using a unique suffix per run makes the state
    change observable.
    """
    return f"e2e_{E2E_RUN_ID}_{suffix}"
