"""VaultWatch — AgentWallet: CSPR.click AI Agent Skill integration.

Replaces manual key management with a programmatic agent-wallet abstraction.

Why this module exists
----------------------
The CSPR.click AI Agent Skill (``skills/csprclick-skill/SKILL.md``) teaches
how to integrate the CSPR.click Web SDK for **browser-based** wallet
operations. The Web SDK is browser-only — every signature requires a human
to approve in their wallet UI.

For headless / autonomous agent workflows (pytest e2e tests, MCP server
deploys, scheduled pipeline writes), the skill's reference implementation
(`Autarca <https://github.com/AK-Bit-Lab/Autarca>`_) uses the same
``casper-js-sdk`` v5 that CSPR.click uses under the hood, but loads the
agent keypair from a server-side PEM file instead of a browser wallet.

This module implements that server-side agent-wallet pattern, with one
critical improvement over the prior "manual key management" approach:

    The agent keypair is CREATED PROGRAMMATICALLY via
    ``PrivateKey.generate(KeyAlgorithm.SECP256K1)`` — no external keygen,
    no manually-imported .pem files, no committed secrets. The key lives
    at ``$VAULTWATCH_AGENT_KEY_PATH`` (default ``~/.vaultwatch/agent_key.pem``)
    which is gitignored. On first run, ``AgentWallet.ensure_exists()`` CREATES
    the key + logs the public key + the testnet faucet URL so the operator
    can fund it.

Usage
-----
    from vaultwatch.agents.agent_wallet import AgentWallet

    # 1. Ensure an agent wallet exists (creates one on first run)
    wallet = AgentWallet.ensure_exists()

    # 2. Inspect it
    print(wallet.public_key)        # '0203...'
    print(wallet.account_hash)      # 'account-hash-...'
    print(wallet.balance_cspr)      # 1234.5  (or None if unfunded)

    # 3. Sign + submit a deploy (delegates to scripts/casper_call.cjs)
    result = wallet.call_contract(
        contract_hash='cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932',
        entry_point='record_finding',
        args={'agent_name': {'type': 'string', 'value': 'AnomalyAgent'}, ...},
    )

Backward compatibility
----------------------
The legacy ``CasperContractClient(signing_key_path=...)`` API still works —
it now delegates to ``AgentWallet`` internally. Existing callers do not need
to change.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — defaults match scripts/csprclick_agent_wallet.cjs
# ---------------------------------------------------------------------------

#: Default agent key path (gitignored — NEVER committed to the repo).
DEFAULT_AGENT_KEY_PATH = Path.home() / ".vaultwatch" / "agent_key.pem"

#: Default key algorithm (SECP256K1 matches the existing funded Account-2 key
#: so the abstraction is drop-in compatible with the prior manual key).
DEFAULT_KEY_ALGORITHM = "secp256k1"

#: Default Casper testnet RPC endpoint.
DEFAULT_RPC_URL = "https://node.testnet.casper.network/rpc"

#: Default Casper testnet chain name.
DEFAULT_CHAIN_NAME = "casper-test"

#: Testnet faucet URL (printed on first-run wallet creation).
FAUCET_URL = "https://testnet.cspr.live/tools/faucet"

#: Root of the vaultwatch package (so we can locate scripts/).
#: __file__ = .../vaultwatch/agents/agent_wallet.py
#: .parent = .../vaultwatch/agents/
#: .parent.parent = .../vaultwatch/   ← package root (contains scripts/, tests/, etc.)
_PKG_ROOT = Path(__file__).resolve().parent.parent

#: Path to the Node helper that does the actual crypto.
_AGENT_WALLET_HELPER = _PKG_ROOT / "scripts" / "csprclick_agent_wallet.cjs"

#: Path to the Node helper that signs + submits deploys.
_CALL_HELPER = _PKG_ROOT / "scripts" / "casper_call.cjs"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AgentWalletError(RuntimeError):
    """Raised when the AgentWallet helper fails or the wallet is missing."""


class AgentWalletUnfunded(AgentWalletError):
    """Raised when the agent wallet exists but has zero CSPR balance."""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentWallet:
    """Server-side Casper agent wallet abstraction.

    Wraps ``scripts/csprclick_agent_wallet.cjs`` (programmatic keypair
    creation + info) and ``scripts/casper_call.cjs`` (deploy signing +
    submission + on-chain verification).

    Attributes
    ----------
    key_path : Path
        Filesystem path where the agent's PEM secret key is stored
        (mode 0600, gitignored).
    public_key : str
        The agent's Casper public key (66-hex-char, e.g.
        ``02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db``).
    account_hash : str
        The agent's account hash (``account-hash-<64 hex>``).
    key_algorithm : str
        ``"secp256k1"`` or ``"ed25519"``.
    chain_name : str
        Casper chain identifier (``"casper-test"`` for testnet).
    rpc_url : str
        JSON-RPC endpoint URL.
    balance_motes : Optional[int]
        Wallet balance in motes (1 CSPR = 1e9 motes), or ``None`` if the
        account does not exist on-chain yet (unfunded).
    """

    key_path: Path
    public_key: str
    account_hash: str
    key_algorithm: str = DEFAULT_KEY_ALGORITHM
    chain_name: str = DEFAULT_CHAIN_NAME
    rpc_url: str = DEFAULT_RPC_URL
    balance_motes: Optional[int] = None
    _info_cache: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def ensure_exists(
        cls,
        *,
        key_path: Optional[Path] = None,
        key_algorithm: str = DEFAULT_KEY_ALGORITHM,
        rpc_url: str = DEFAULT_RPC_URL,
        chain_name: str = DEFAULT_CHAIN_NAME,
        create_if_missing: bool = True,
    ) -> "AgentWallet":
        """Return an :class:`AgentWallet` for the configured key path.

        If no agent key exists at ``key_path`` (default
        ``$VAULTWATCH_AGENT_KEY_PATH`` or ``~/.vaultwatch/agent_key.pem``)
        and ``create_if_missing`` is True, **programmatically creates** a
        new SECP256K1 keypair via ``PrivateKey.generate()`` (in the Node
        helper) and prints the faucet URL.

        Raises :class:`AgentWalletError` if the helper fails or the wallet
        is missing and ``create_if_missing`` is False.
        """
        path = Path(key_path or os.getenv("VAULTWATCH_AGENT_KEY_PATH") or DEFAULT_AGENT_KEY_PATH)
        if not path.exists():
            if not create_if_missing:
                raise AgentWalletError(
                    f"No agent wallet at {path}. Run "
                    f"`node scripts/csprclick_agent_wallet.cjs create` first."
                )
            cls._create_keypair(path, key_algorithm, rpc_url, chain_name)

        return cls.load(key_path=path, rpc_url=rpc_url, chain_name=chain_name)

    @classmethod
    def load(
        cls,
        *,
        key_path: Optional[Path] = None,
        rpc_url: str = DEFAULT_RPC_URL,
        chain_name: str = DEFAULT_CHAIN_NAME,
    ) -> "AgentWallet":
        """Load an existing agent wallet (does NOT create one if missing)."""
        path = Path(key_path or os.getenv("VAULTWATCH_AGENT_KEY_PATH") or DEFAULT_AGENT_KEY_PATH)
        if not path.exists():
            raise AgentWalletError(
                f"No agent wallet at {path}. Run "
                f"`node scripts/csprclick_agent_wallet.cjs create` first "
                f"or call AgentWallet.ensure_exists(create_if_missing=True)."
            )
        # Pass the key path via env var so the Node helper reads the correct file.
        env = cls._env_with(rpc_url=rpc_url, chain_name=chain_name, key_path=path)
        info = cls._run_helper(["info"], env=env, rpc_url=rpc_url, chain_name=chain_name)
        if not info.get("ok"):
            raise AgentWalletError(f"agent_wallet.cjs info failed: {info.get('error')}")
        return cls(
            key_path=path,
            public_key=info["public_key"],
            account_hash=info["account_hash"],
            key_algorithm=info.get("key_algorithm", DEFAULT_KEY_ALGORITHM),
            chain_name=info.get("chain_name", chain_name),
            rpc_url=info.get("rpc_url", rpc_url),
            balance_motes=info.get("balance_motes"),
            _info_cache=info,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def balance_cspr(self) -> Optional[float]:
        """Wallet balance in whole CSPR (float), or ``None`` if unfunded."""
        if self.balance_motes is None:
            return None
        return self.balance_motes / 1_000_000_000

    @property
    def funded(self) -> bool:
        """True iff the wallet has a non-zero on-chain CSPR balance."""
        return self.balance_motes is not None and self.balance_motes > 0

    @property
    def faucet_url(self) -> str:
        return FAUCET_URL

    @property
    def explorer_url(self) -> str:
        return f"https://testnet.cspr.live/account/{self.public_key}"

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    def refresh_balance(self) -> Optional[int]:
        """Re-query the wallet balance from the RPC node (mutates self)."""
        env = self._env_with(
            rpc_url=self.rpc_url,
            chain_name=self.chain_name,
            key_path=self.key_path,
            key_algorithm=self.key_algorithm,
        )
        info = self._run_helper(["info"], env=env, rpc_url=self.rpc_url, chain_name=self.chain_name)
        if not info.get("ok"):
            raise AgentWalletError(f"refresh_balance failed: {info.get('error')}")
        self.balance_motes = info.get("balance_motes")
        return self.balance_motes

    def assert_funded(self, min_cspr: float = 1.0) -> None:
        """Raise :class:`AgentWalletUnfunded` if balance is below ``min_cspr``."""
        if self.balance_motes is None:
            raise AgentWalletUnfunded(
                f"Agent wallet {self.public_key} has no on-chain account yet. "
                f"Fund it at {self.faucet_url} (paste the public key)."
            )
        bal_cspr = self.balance_motes / 1_000_000_000
        if bal_cspr < min_cspr:
            raise AgentWalletUnfunded(
                f"Agent wallet {self.public_key} balance {bal_cspr:.2f} CSPR "
                f"is below the minimum {min_cspr:.2f} CSPR. "
                f"Refill at {self.faucet_url}."
            )

    def call_contract(
        self,
        *,
        contract_hash: str,
        entry_point: str,
        args: Dict[str, Dict[str, Any]],
        payment_motes: int = 5_000_000_000,
        verify_timeout_ms: int = 120_000,
    ) -> Dict[str, Any]:
        """Sign + submit + verify a stored-contract deploy using this agent wallet.

        Delegates to ``scripts/casper_call.cjs`` (casper-js-sdk v5
        ``ContractCallBuilder``). The helper auto-loads the agent key from
        ``self.key_path`` — no manual ``signer_pem_path`` required.

        Args:
            contract_hash: 64-hex contract hash (with or without ``hash-`` prefix).
            entry_point: on-chain entry point name.
            args: typed-args dict ``{name: {"type": "string|bool|u8|u64|u512",
                "value": "..."}}``.
            payment_motes: gas payment in motes (default 5 CSPR).
            verify_timeout_ms: how long to poll for the deploy to commit.

        Returns:
            The helper's JSON response (``success``, ``deploy_hash``,
            ``block_hash``, ``cost_motes``, ``link``, ``error``).
        """
        payload = {
            "contract_hash": contract_hash.replace("hash-", ""),
            "entry_point": entry_point,
            "args": args,
            "payment_motes": payment_motes,
            "signer_pem_path": str(self.key_path),
            "key_algorithm": self.key_algorithm,
            "rpc_url": self.rpc_url,
            "verify_timeout_ms": verify_timeout_ms,
        }
        return self._run_call_helper(payload)

    def transfer_cspr(
        self,
        *,
        to_public_key: str,
        amount_motes: int,
        payment_motes: int = 5_000_000_000,
        verify_timeout_ms: int = 120_000,
    ) -> Dict[str, Any]:
        """Sign + submit + verify a native CSPR transfer deploy.

        Builds a ``TransferV1`` deploy via casper-js-sdk, signs with the
        agent key, submits, and verifies on-chain.

        Args:
            to_public_key: recipient public key (66-hex).
            amount_motes: transfer amount in motes (1 CSPR = 1e9 motes).
            payment_motes: gas payment in motes (default 5 CSPR).
            verify_timeout_ms: how long to poll for the deploy to commit.

        Returns:
            The helper's JSON response (same shape as :meth:`call_contract`).
        """
        payload = {
            "transfer": True,
            "to_public_key": to_public_key,
            "amount_motes": str(amount_motes),
            "payment_motes": payment_motes,
            "signer_pem_path": str(self.key_path),
            "key_algorithm": self.key_algorithm,
            "rpc_url": self.rpc_url,
            "chain_name": self.chain_name,
            "verify_timeout_ms": verify_timeout_ms,
        }
        return self._run_call_helper(payload)

    # ------------------------------------------------------------------
    # Internal: subprocess helpers
    # ------------------------------------------------------------------

    @classmethod
    def _create_keypair(
        cls,
        path: Path,
        key_algorithm: str,
        rpc_url: str,
        chain_name: str,
    ) -> None:
        """Programmatically generate a new agent keypair via the Node helper."""
        env = cls._env_with(rpc_url=rpc_url, chain_name=chain_name, key_path=path, key_algorithm=key_algorithm)
        result = cls._run_helper(["create", "--force"], env=env, rpc_url=rpc_url, chain_name=chain_name)
        if not result.get("ok"):
            raise AgentWalletError(f"agent_wallet.cjs create failed: {result.get('error')}")
        logger.info(
            "Created NEW agent wallet: public_key=%s account_hash=%s\n"
            "  Fund it at: %s\n"
            "  Explorer:   %s",
            result.get("public_key"),
            result.get("account_hash"),
            result.get("faucet_url"),
            result.get("explorer_url"),
        )

    @staticmethod
    def _env_with(
        *,
        rpc_url: str = DEFAULT_RPC_URL,
        chain_name: str = DEFAULT_CHAIN_NAME,
        key_path: Optional[Path] = None,
        key_algorithm: str = DEFAULT_KEY_ALGORITHM,
    ) -> Dict[str, str]:
        env = dict(os.environ)
        env["CASPER_RPC_URL"] = rpc_url
        env["CASPER_CHAIN_NAME"] = chain_name
        env["VAULTWATCH_AGENT_KEY_ALGO"] = key_algorithm
        if key_path is not None:
            env["VAULTWATCH_AGENT_KEY_PATH"] = str(key_path)
        return env

    @classmethod
    def _run_helper(
        cls,
        args: list,
        *,
        env: Optional[Dict[str, str]] = None,
        rpc_url: str = DEFAULT_RPC_URL,
        chain_name: str = DEFAULT_CHAIN_NAME,
    ) -> Dict[str, Any]:
        """Run ``scripts/csprclick_agent_wallet.cjs`` with the given args."""
        if not _AGENT_WALLET_HELPER.exists():
            raise AgentWalletError(f"agent_wallet.cjs helper not found at {_AGENT_WALLET_HELPER}")
        if env is None:
            env = cls._env_with(rpc_url=rpc_url, chain_name=chain_name)
        try:
            proc = subprocess.run(
                ["node", str(_AGENT_WALLET_HELPER), *args],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
        except subprocess.TimeoutExpired as e:
            raise AgentWalletError(f"agent_wallet.cjs {args[0]} timed out") from e
        if proc.returncode != 0:
            raise AgentWalletError(
                f"agent_wallet.cjs {args[0]} exited {proc.returncode}: "
                f"{proc.stderr.strip()[:500] or proc.stdout.strip()[:500]}"
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise AgentWalletError(
                f"agent_wallet.cjs {args[0]} returned non-JSON: {proc.stdout[:500]}"
            ) from e

    def _run_call_helper(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run ``scripts/casper_call.cjs`` with the given JSON payload."""
        if not _CALL_HELPER.exists():
            raise AgentWalletError(f"casper_call.cjs helper not found at {_CALL_HELPER}")
        timeout = (payload.get("verify_timeout_ms", 120_000) // 1000) + 60
        try:
            proc = subprocess.run(
                ["node", str(_CALL_HELPER)],
                input=json.dumps(payload).encode("utf-8"),
                capture_output=True,
                timeout=timeout,
                cwd=str(_PKG_ROOT),
            )
        except subprocess.TimeoutExpired as e:
            raise AgentWalletError(f"casper_call.cjs timed out after {timeout}s") from e
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[:1000]
            raise AgentWalletError(
                f"casper_call.cjs exited {proc.returncode}: {stderr}"
            )
        try:
            return json.loads(proc.stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise AgentWalletError(
                f"casper_call.cjs returned non-JSON: {proc.stdout[:500]}"
            ) from e


# ---------------------------------------------------------------------------
# Convenience: lazy module-level singleton (for scripts that just want "the" wallet)
# ---------------------------------------------------------------------------

_WALLET_SINGLETON: Optional[AgentWallet] = None


def get_agent_wallet() -> AgentWallet:
    """Return the process-wide :class:`AgentWallet` singleton.

    Creates one on first call (via :meth:`AgentWallet.ensure_exists`).
    """
    global _WALLET_SINGLETON
    if _WALLET_SINGLETON is None:
        _WALLET_SINGLETON = AgentWallet.ensure_exists()
    return _WALLET_SINGLETON


__all__ = [
    "AgentWallet",
    "AgentWalletError",
    "AgentWalletUnfunded",
    "get_agent_wallet",
    "DEFAULT_AGENT_KEY_PATH",
    "DEFAULT_KEY_ALGORITHM",
    "DEFAULT_RPC_URL",
    "DEFAULT_CHAIN_NAME",
    "FAUCET_URL",
]
