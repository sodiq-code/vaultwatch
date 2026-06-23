"""
VaultWatch — Casper Contract Client
Wraps casper-python-sdk for deploy + contract call operations.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("vaultwatch.casper_client")

# ---------------------------------------------------------------------------
# Optional SDK import — fall back gracefully so tests run without a node
# ---------------------------------------------------------------------------
try:
    from pycspr import NodeRpcClient, NodeRpcConnectionInfo, KeyAlgorithm  # type: ignore
    from pycspr import create_deploy_parameters, create_standard_payment, get_signature  # type: ignore
    from pycspr import get_key_pair_from_pem_file, get_account_hash  # type: ignore

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
        REST endpoint of the Casper node (e.g. ``http://localhost:7777``).
    chain_name : str
        Network identifier, e.g. ``casper-test`` for testnet.
    signing_key_path : str
        Path to the operator secret key (PEM format).
    mock : bool
        If *True* all blockchain calls are no-ops; useful for unit tests.
    """

    def __init__(
        self,
        node_url: str = "",
        chain_name: str = "casper-test",
        signing_key_path: str = "",
        mock: bool = False,
    ) -> None:
        self.node_url = node_url or os.getenv(
            "CASPER_NODE_URL", "http://localhost:7777"
        )
        self.chain_name = chain_name or os.getenv("CASPER_CHAIN_NAME", "casper-test")
        self.signing_key_path = signing_key_path or os.getenv(
            "CASPER_SIGNING_KEY_PATH", ""
        )
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
            # Parse the node URL to extract host and port
            # Expected format: https://rpc.testnet.casperlabs.io/rpc or http://localhost:7777
            url = self.node_url.replace("https://", "").replace("http://", "").split("/")[0]
            host = url.split(":")[0]
            port = int(url.split(":")[-1]) if ":" in url else 7777
            
            conn = NodeRpcConnectionInfo(host=host, port=port)
            self._client = NodeRpcClient(conn)
            logger.info("Casper node RPC client initialised — %s (host=%s, port=%d)", self.node_url, host, port)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to init Casper RPC client: %s", exc)
            self.mock = True

    def _load_key(self) -> Any:
        if self._account_key is not None:
            return self._account_key
        if not self.signing_key_path:
            raise RuntimeError("No signing key path configured")
        
        # Use get_key_pair_from_pem_file to load the private key
        self._account_key = get_key_pair_from_pem_file(self.signing_key_path)
        return self._account_key

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
                block = self._client.get_block()  # type: ignore[union-attr]
                height = block["header"]["height"]
                span.set_attribute("block_height", height)
                return height
            except Exception as exc:  # pragma: no cover
                logger.error("get_block_height failed: %s", exc)
                return 0

    def deploy_contract(
        self,
        wasm_path: str,
        args: Dict[str, Any],
        payment_amount: int = 100_000_000_000,
    ) -> str:
        """
        Deploy a contract WASM to the network.

        Returns the deploy hash as a hex string.
        """
        with tracer.start_as_current_span("casper.deploy_contract") as span:
            span.set_attribute("wasm_path", wasm_path)
            span.set_attribute("payment_motes", payment_amount)

            if self.mock:
                import hashlib

                mock_hash = hashlib.sha256(
                    f"{wasm_path}{time.time()}".encode()
                ).hexdigest()
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
                payment=payment_amount,
            )
            session = ExecutableDeployItem.new_module_bytes(wasm_bytes, args)  # type: ignore
            deploy = Deploy(params, session)
            deploy.approve(key)
            deploy_hash = self._client.send_deploy(deploy)  # type: ignore[union-attr]
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

                mock_hash = hashlib.sha256(
                    f"{contract_hash}{entry_point}{time.time()}".encode()
                ).hexdigest()
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
                payment=payment_amount,
            )
            session = ExecutableDeployItem.new_stored_contract_by_hash(  # type: ignore
                contract_hash.encode(),
                entry_point,
                args,
            )
            deploy = Deploy(params, session)
            deploy.approve(key)
            deploy_hash = self._client.send_deploy(deploy)  # type: ignore[union-attr]
            span.set_attribute("deploy_hash", deploy_hash)
            return deploy_hash

    def query_contract_state(
        self,
        contract_hash: str,
        path: List[str],
    ) -> Any:
        """
        Query a named key inside a contract's state.

        Returns the raw decoded value, or ``None`` on error.
        """
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
            except Exception as exc:  # pragma: no cover
                logger.error("query_contract_state failed: %s", exc)
                return None

    def wait_for_deploy(
        self,
        deploy_hash: str,
        timeout: int = 120,
        poll_interval: int = 5,
    ) -> bool:
        """
        Poll until *deploy_hash* is included in a block.

        Returns ``True`` on success, ``False`` on timeout.
        """
        with tracer.start_as_current_span("casper.wait_for_deploy") as span:
            span.set_attribute("deploy_hash", deploy_hash)

            if self.mock:
                span.set_attribute("mock", True)
                return True

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    result = self._client.get_deploy(deploy_hash)  # type: ignore[union-attr]
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
                return 1_000_000_000_000  # 1000 CSPR mock balance

            try:
                balance = self._client.get_account_balance(  # type: ignore[union-attr]
                    purse_uref=None,
                    account_hash=account_hash,
                )
                span.set_attribute("balance_motes", balance)
                return balance
            except Exception as exc:  # pragma: no cover
                logger.error("get_account_balance failed: %s", exc)
                return 0
