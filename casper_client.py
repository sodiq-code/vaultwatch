"""
VaultWatch — Casper Contract Client
Wraps casper-python-sdk (pycspr 1.2.0) for deploy + contract call operations.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("vaultwatch.casper_client")

# ---------------------------------------------------------------------------
# Optional SDK import — fall back gracefully so tests run without a node
# ---------------------------------------------------------------------------
try:
    from pycspr import NodeRpcClient, NodeRpcConnectionInfo  # type: ignore
    from pycspr.factory import (  # type: ignore
        create_deploy,
        create_deploy_parameters,
        parse_private_key,
    )
    from pycspr.types.crypto import KeyAlgorithm  # type: ignore
    from pycspr.types.cl import CLV_U512  # type: ignore
    from pycspr.types.node.rpc.complex import (  # type: ignore
        DeployArgument,
        DeployOfModuleBytes,
        DeployOfStoredContractByHash,
    )

    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SDK_AVAILABLE = False
    logger.warning("casper-python-sdk not installed — running in mock mode")


class CasperContractClient:
    """
    Thin wrapper around the Casper Python SDK for VaultWatch contract ops.

    Parameters
    ----------
    node_url : str
        RPC endpoint of the Casper node (e.g. ``http://node.testnet.casper.network``).
    chain_name : str
        Network identifier — ``casper-test`` for testnet.
    signing_key_path : str
        Path to the operator secret key (PEM format, SECP256K1).
    mock : bool
        If *True* all blockchain calls are no-ops — useful for unit tests.
    """

    def __init__(
        self,
        node_url: str = "",
        chain_name: str = "casper-test",
        signing_key_path: str = "",
        mock: bool = False,
    ) -> None:
        self.node_url = node_url or os.getenv("CASPER_NODE_URL", "http://node.testnet.casper.network")
        self.chain_name = chain_name or os.getenv("CASPER_CHAIN_NAME", "casper-test")
        self.signing_key_path = signing_key_path or os.getenv("CASPER_SIGNING_KEY_PATH", "")
        self.mock = mock or not _SDK_AVAILABLE

        self._client: Optional[Any] = None
        self._account_key: Optional[Any] = None

        if not self.mock:
            self._init_client()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_client(self) -> None:
        try:
            url = self.node_url.replace("https://", "").replace("http://", "").split("/")[0]
            host = url.split(":")[0]
            port = int(url.split(":")[-1]) if ":" in url else 7777
            conn = NodeRpcConnectionInfo(host=host, port=port)
            self._client = NodeRpcClient(conn)
            logger.info("Casper RPC client ready — %s:%d", host, port)
        except Exception as exc:
            logger.error("Failed to init Casper RPC client: %s", exc)
            self.mock = True

    def _load_key(self) -> Any:
        """Load and cache the SECP256K1 private key from PEM file."""
        if self._account_key is not None:
            return self._account_key
        if not self.signing_key_path:
            raise RuntimeError("No signing key path configured")
        self._account_key = parse_private_key(Path(self.signing_key_path), KeyAlgorithm.SECP256K1)
        return self._account_key

    def _make_standard_payment(self, amount_motes: int) -> "DeployOfModuleBytes":
        """
        Standard Casper payment: empty module_bytes with CLV_U512 amount arg.
        pycspr 1.2.0 requires DeployArgument(name, CLValue) objects in args list.
        """
        return DeployOfModuleBytes(
            module_bytes=b"",
            args=[DeployArgument(name="amount", value=CLV_U512(amount_motes))],
        )

    @staticmethod
    def _normalise_args(args: Any) -> list:
        """
        Convert a plain dict of {name: value} into [DeployArgument(name, CLValue)].
        If args is already a list, return as-is.
        Supports int → CLV_U512, str → CLV_String, bool → CLV_Bool.
        """
        if isinstance(args, list):
            return args
        if not args:
            return []
        from pycspr.types.cl import CLV_String, CLV_Bool, CLV_U512  # type: ignore

        result = []
        for name, value in args.items():
            if isinstance(value, bool):
                cl_val = CLV_Bool(value)
            elif isinstance(value, int):
                cl_val = CLV_U512(value)
            elif isinstance(value, str):
                cl_val = CLV_String(value)
            else:
                cl_val = value  # assume already a CLValue
            result.append(DeployArgument(name=name, value=cl_val))
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_block_height(self) -> int:
        """Return the latest block height from the node."""
        with tracer.start_as_current_span("casper.get_block_height") as span:
            if self.mock:
                mock_height = int(time.time()) % 1_000_000
                span.set_attribute("mock", True)
                return mock_height
            try:
                block = asyncio.run(self._client.get_block())  # type: ignore[union-attr]
                height = block["header"]["height"]
                span.set_attribute("block_height", height)
                return height
            except Exception as exc:
                logger.error("get_block_height failed: %s", exc)
                return 0

    def deploy_contract(
        self,
        wasm_path: str,
        args: Dict[str, Any],
        payment_amount: int = 100_000_000_000,
    ) -> str:
        """
        Deploy a WASM contract to the Casper network.
        Returns the deploy hash as a hex string.
        """
        with tracer.start_as_current_span("casper.deploy_contract") as span:
            span.set_attribute("wasm_path", wasm_path)
            span.set_attribute("payment_motes", payment_amount)

            if self.mock:
                import hashlib

                mock_hash = hashlib.sha256(f"{wasm_path}{time.time()}".encode()).hexdigest()
                logger.info("[MOCK] deploy_contract -> %s", mock_hash)
                span.set_attribute("mock", True)
                span.set_attribute("deploy_hash", mock_hash)
                return mock_hash

            key = self._load_key()

            with open(wasm_path, "rb") as fh:
                wasm_bytes = fh.read()

            params = create_deploy_parameters(
                account=key,
                chain_name=self.chain_name,
            )
            payment = self._make_standard_payment(payment_amount)
            # Convert plain dict args to DeployArgument list if needed
            session_args = self._normalise_args(args)
            session = DeployOfModuleBytes(module_bytes=wasm_bytes, args=session_args)

            deploy = create_deploy(params, payment, session)
            deploy.approve(key)

            deploy_hash = asyncio.run(
                self._client.account_put_deploy(deploy)  # type: ignore[union-attr]
            )
            if hasattr(deploy_hash, "hex"):
                deploy_hash = deploy_hash.hex()
            deploy_hash = str(deploy_hash)

            span.set_attribute("deploy_hash", deploy_hash)
            logger.info("Contract deployed — hash: %s", deploy_hash)
            return deploy_hash

    def call_contract(
        self,
        contract_hash: str,
        entry_point: str,
        args: Dict[str, Any],
        payment_amount: int = 5_000_000_000,
    ) -> str:
        """
        Call a stored contract entry point.
        Returns the deploy hash.
        """
        with tracer.start_as_current_span("casper.call_contract") as span:
            span.set_attribute("contract_hash", contract_hash)
            span.set_attribute("entry_point", entry_point)

            if self.mock:
                import hashlib

                mock_hash = hashlib.sha256(f"{contract_hash}{entry_point}{time.time()}".encode()).hexdigest()
                logger.info(
                    "[MOCK] call_contract(%s::%s) -> %s",
                    contract_hash,
                    entry_point,
                    mock_hash,
                )
                span.set_attribute("mock", True)
                span.set_attribute("deploy_hash", mock_hash)
                return mock_hash

            key = self._load_key()
            params = create_deploy_parameters(
                account=key,
                chain_name=self.chain_name,
            )
            payment = self._make_standard_payment(payment_amount)

            # contract_hash may arrive as hex string — convert to bytes
            hash_bytes = bytes.fromhex(contract_hash) if isinstance(contract_hash, str) else contract_hash
            session_args = self._normalise_args(args)
            session = DeployOfStoredContractByHash(
                hash=hash_bytes,
                entry_point=entry_point,
                args=session_args,
            )

            deploy = create_deploy(params, payment, session)
            deploy.approve(key)

            deploy_hash = asyncio.run(
                self._client.account_put_deploy(deploy)  # type: ignore[union-attr]
            )
            if hasattr(deploy_hash, "hex"):
                deploy_hash = deploy_hash.hex()
            deploy_hash = str(deploy_hash)

            span.set_attribute("deploy_hash", deploy_hash)
            return deploy_hash

    async def call_contract_real(
        self,
        contract_hash: str,
        entry_point: str,
        args: Dict[str, Any],
        payment_amount: int = 5_000_000_000,
        typed_args: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Submit a REAL stored-contract deploy to Casper testnet via the
        official casper-js-sdk v5 Node.js helper.

        ``CasperContractClient.call_contract`` (above) uses pycspr, whose
        deploy signatures Casper 2.x rejects with "invalid approval" (see
        worklog Task 1). The sanctioned path for real writes is to shell out
        to ``scripts/casper_call.cjs`` (casper-js-sdk v5 ContractCallBuilder)
        — the same helper the MCP server uses for all real deploys.

        Args:
            contract_hash: 64-hex contract hash (with or without ``hash-`` prefix).
            entry_point: the contract entry-point name.
            args: plain dict of {name: value}. If ``typed_args`` is None, the
                values are typed heuristically (str→string, bool→bool,
                int→u512/u64). For exact control, pass ``typed_args`` with
                the explicit {name: {"type": "string|bool|u8|u64|u512", "value": "..."}}.
            payment_amount: gas payment in motes (default 5 CSPR).
            typed_args: explicit typed args (overrides ``args`` when provided).

        Returns:
            The helper's JSON response: ``{"success": bool, "deploy_hash": str,
            "block_hash": str, "cost_motes": str, "link": str, "error": str|None}``.

        Raises:
            RuntimeError: if the helper is missing or the deploy fails to submit.
        """
        with tracer.start_as_current_span("casper.call_contract_real") as span:
            span.set_attribute("contract_hash", contract_hash)
            span.set_attribute("entry_point", entry_point)

            helper = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "scripts",
                "casper_call.cjs",
            )
            if not os.path.exists(helper):
                raise RuntimeError(f"casper_call.cjs helper not found: {helper}")

            # Build typed args — prefer explicit typed_args, else infer from plain dict
            if typed_args is None:
                typed_args = _infer_typed_args(args)

            payload: Dict[str, Any] = {
                "contract_hash": contract_hash.replace("hash-", ""),
                "entry_point": entry_point,
                "args": typed_args,
                "payment_motes": payment_amount,
            }
            # Attach the operator signing key if available
            pem = self.signing_key_path or os.getenv("CASPER_SIGNING_KEY_PATH", "")
            if pem and os.path.exists(pem):
                payload["signer_pem_path"] = pem
            if os.getenv("CASPER_RPC_URL"):
                payload["rpc_url"] = os.environ["CASPER_RPC_URL"]
            if os.getenv("VAULTWATCH_SIGNER_ALGO"):
                payload["key_algorithm"] = os.environ["VAULTWATCH_SIGNER_ALGO"]

            span.set_attribute("args_count", len(typed_args))

            proc = await asyncio.create_subprocess_exec(
                "node",
                helper,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(
                json.dumps(payload).encode("utf-8")
            )
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()[:500]
                span.set_attribute("error", err)
                raise RuntimeError(f"casper_call.cjs exited {proc.returncode}: {err}")
            result = json.loads(stdout.decode("utf-8"))
            span.set_attribute("deploy_hash", result.get("deploy_hash", ""))
            span.set_attribute("success", result.get("success", False))
            return result

    def query_contract_state(
        self,
        contract_hash: str,
        path: List[str],
    ) -> Any:
        """Query a named key inside a contract's state."""
        with tracer.start_as_current_span("casper.query_contract_state") as span:
            span.set_attribute("contract_hash", contract_hash)
            span.set_attribute("path", ".".join(path))

            if self.mock:
                span.set_attribute("mock", True)
                return {"mock": True, "value": None}

            try:
                state = self._client.query_global_state(  # type: ignore[union-attr]
                    state_root_hash=None,
                    key=f"hash-{contract_hash}",
                    path=path,
                )
                return state
            except Exception as exc:
                logger.error("query_contract_state failed: %s", exc)
                return None

    def wait_for_deploy(
        self,
        deploy_hash: str,
        timeout: int = 120,
        poll_interval: int = 5,
    ) -> bool:
        """Poll until deploy_hash is included in a block. Returns True on success."""
        with tracer.start_as_current_span("casper.wait_for_deploy") as span:
            span.set_attribute("deploy_hash", deploy_hash)

            if self.mock:
                span.set_attribute("mock", True)
                return True

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    result = asyncio.run(
                        self._client.get_deploy(deploy_hash)  # type: ignore[union-attr]
                    )
                    if result.get("execution_results"):
                        span.set_attribute("success", True)
                        return True
                except Exception:
                    pass
                time.sleep(poll_interval)

            span.set_attribute("success", False)
            logger.warning("wait_for_deploy timed out for %s", deploy_hash)
            return False

    def get_account_balance(self, account_hash: str) -> int:
        """Return the CSPR balance (in motes) for an account hash."""
        with tracer.start_as_current_span("casper.get_account_balance") as span:
            span.set_attribute("account_hash", account_hash)

            if self.mock:
                span.set_attribute("mock", True)
                return 1_000_000_000_000  # 1000 CSPR mock

            try:
                balance = self._client.get_account_balance(  # type: ignore[union-attr]
                    purse_uref=None,
                    account_hash=account_hash,
                )
                span.set_attribute("balance_motes", balance)
                return balance
            except Exception as exc:
                logger.error("get_account_balance failed: %s", exc)
                return 0


# ---------------------------------------------------------------------------
# Typed-args inference for the Node.js helper (casper_call.cjs)
# ---------------------------------------------------------------------------
def _infer_typed_args(args: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Convert a plain ``{name: value}`` dict into the typed-args schema
    expected by ``scripts/casper_call.cjs``.

    Mapping (matches the CL types accepted by casper-js-sdk v5):
      - ``bool``   → ``{"type": "bool",   "value": str(bool).lower()}``
      - ``int``    → ``{"type": "u512",   "value": str(int)}``  (large ints default to u512)
      - ``str``    → ``{"type": "string", "value": str}``
      - already-typed ``{"type": ..., "value": ...}`` dicts are passed through.
    """
    typed: Dict[str, Dict[str, Any]] = {}
    for name, value in (args or {}).items():
        if isinstance(value, dict) and "type" in value and "value" in value:
            typed[name] = value
            continue
        if isinstance(value, bool):
            typed[name] = {"type": "bool", "value": "true" if value else "false"}
        elif isinstance(value, int):
            # u512 covers the full u64/u128 range; casper_call.cjs accepts decimal strings.
            typed[name] = {"type": "u512", "value": str(value)}
        else:
            typed[name] = {"type": "string", "value": str(value)}
    return typed
