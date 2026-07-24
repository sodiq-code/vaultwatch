"""
VaultWatch SDK — VaultWatchClient
Async HTTP client wrapping the VaultWatch REST API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("vaultwatch.sdk")


class AuditTrailNamespace:
    """Direct on-chain query methods for the ``AuditTrail`` contract.

    Every method hits the VaultWatch FastAPI proxy (``/chain/*``), which in
    turn performs a real ``query_global_state`` JSON-RPC read against the
    Casper testnet node. The browser/SDK never talks to the node directly
    and never needs an API key.
    """

    def __init__(self, client: "VaultWatchClient") -> None:
        self._client = client

    async def get_finding(self, finding_id: int) -> Dict[str, Any]:
        """Fetch a single finding by its numeric on-chain ID.

        Corresponds to ``AuditTrail::get_finding(id)``. Returns the finding
        as a dict (``id``, ``protocol``, ``summary``, ``severity``,
        ``confidence``, ``contract_hash``, ``timestamp``, ``source``, …).

        Raises ``httpx.HTTPStatusError`` (404) when the finding does not exist
        on chain or in the proxy's in-memory fallback store.
        """
        return await self._client._get(f"/chain/finding/{int(finding_id)}")

    async def get_findings(self, limit: int = 20) -> Dict[str, Any]:
        """Fetch the latest ``limit`` findings (newest first).

        Returns ``{"count": int, "findings": [...], "source": "on-chain"|"fallback"}``.
        """
        return await self._client._get("/chain/findings", limit=limit)

    async def get_count(self) -> Dict[str, Any]:
        """Return ``AuditTrail.finding_count`` (the on-chain counter)."""
        return await self._client._get("/chain/finding-count")

    # ------------------------------------------------------------------
    # Synchronous wrappers
    # ------------------------------------------------------------------
    def get_finding_sync(self, finding_id: int) -> Dict[str, Any]:
        return asyncio.run(self.get_finding(finding_id))

    def get_findings_sync(self, limit: int = 20) -> Dict[str, Any]:
        return asyncio.run(self.get_findings(limit))

    def get_count_sync(self) -> Dict[str, Any]:
        return asyncio.run(self.get_count())


class RiskOracleNamespace:
    """Direct on-chain query methods for the ``RiskOracle`` contract."""

    def __init__(self, client: "VaultWatchClient") -> None:
        self._client = client

    async def get_score(self, address: str) -> Dict[str, Any]:
        """Fetch the on-chain risk score for ``address``.

        Corresponds to ``RiskOracle::get_risk_score(address)``. ``address`` is
        the String key the contract stores (typically a Casper account-hash
        string like ``"account-hash-<hex>"``). Returns the parsed ``RiskScore``
        dict (``address``, ``score``, ``risk_type``, ``confidence``,
        ``last_updated``, ``finding_id``, ``source``).

        Raises ``httpx.HTTPStatusError`` (404) when no score exists for the
        address on chain.
        """
        from urllib.parse import quote

        return await self._client._get(f"/chain/risk-score/{quote(address, safe='')}")

    # ------------------------------------------------------------------
    # Synchronous wrappers
    # ------------------------------------------------------------------
    def get_score_sync(self, address: str) -> Dict[str, Any]:
        return asyncio.run(self.get_score(address))


class VaultWatchClient:
    """
    Async client for the VaultWatch REST API.

    Parameters
    ----------
    base_url : str
        Base URL of the VaultWatch API server (e.g. ``http://localhost:8000``).
    api_key : str, optional
        Bearer token for authenticated endpoints.
    timeout : float
        Request timeout in seconds (default 30).

    Examples
    --------
    ::

        async with VaultWatchClient("http://localhost:8000") as client:
            result = await client.query_risk("Analyze Aave liquidity risk")
            print(result)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        # Direct on-chain query namespaces — ``client.audit_trail.get_finding(id)``
        # and ``client.risk_oracle.get_score(address)``. Each method proxies
        # through the VaultWatch FastAPI /chain/* endpoints, which perform real
        # query_global_state RPC reads against the Casper testnet node.
        self.audit_trail = AuditTrailNamespace(self)
        self.risk_oracle = RiskOracleNamespace(self)

    def _auth_headers(self) -> Dict[str, str]:
        """Build the auth header set matching ``api/security.py::AuthMiddleware``.

        The middleware reads the ``X-API-Key`` header (constant-time compared
        via ``hmac.compare_digest``). We send ``X-API-Key`` when ``api_key`` is
        set; a ``Bearer`` fallback is also included for any legacy proxy that
        still reads ``Authorization``.
        """
        if not self.api_key:
            return {}
        return {"X-API-Key": self.api_key, "Authorization": f"Bearer {self.api_key}"}

    async def __aenter__(self) -> "VaultWatchClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
        return self._client

    async def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        resp = await self._http().get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._http().post(path, json=body)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Check API liveness."""
        return await self._get("/health")

    # ------------------------------------------------------------------
    # Risk Intelligence
    # ------------------------------------------------------------------

    async def query_risk(
        self,
        query: str,
        protocol: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ask the IntelAgent a free-form risk question.

        Parameters
        ----------
        query : str
            Natural language question about DeFi risk.
        protocol : str, optional
            Protocol name to scope the analysis.
        context : dict, optional
            Additional context key-value pairs.

        Returns
        -------
        dict
            ``{"status": "ok", "result": {...}}``
        """
        return await self._post(
            "/risk/query",
            {
                "query": query,
                "protocol": protocol,
                "context": context,
            },
        )

    async def get_findings(
        self,
        limit: int = 50,
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return stored risk findings."""
        params: Dict[str, Any] = {"limit": limit}
        if protocol:
            params["protocol"] = protocol
        return await self._get("/risk/findings", **params)

    # ------------------------------------------------------------------
    # Anomaly Detection
    # ------------------------------------------------------------------

    async def detect_anomaly(
        self,
        protocol: str,
        tvl: float,
        volume_24h: float,
        price_change_1h: float,
        num_transactions: int,
        liquidity_ratio: float,
    ) -> Dict[str, Any]:
        """
        Run anomaly detection on protocol metrics.

        Returns risk score (0–100) and detected anomalies.
        """
        return await self._post(
            "/anomaly/detect",
            {
                "protocol": protocol,
                "tvl": tvl,
                "volume_24h": volume_24h,
                "price_change_1h": price_change_1h,
                "num_transactions": num_transactions,
                "liquidity_ratio": liquidity_ratio,
            },
        )

    # ------------------------------------------------------------------
    # RWA Assessment
    # ------------------------------------------------------------------

    async def assess_rwa(
        self,
        asset_id: str,
        asset_type: str,
        issuer: str,
        collateral_ratio: float,
        maturity_days: int,
        credit_rating: str,
    ) -> Dict[str, Any]:
        """Evaluate a real-world asset for on-chain tokenisation."""
        return await self._post(
            "/rwa/assess",
            {
                "asset_id": asset_id,
                "asset_type": asset_type,
                "issuer": issuer,
                "collateral_ratio": collateral_ratio,
                "maturity_days": maturity_days,
                "credit_rating": credit_rating,
            },
        )

    async def list_rwa_assets(self) -> Dict[str, Any]:
        """List all tracked RWA assets."""
        return await self._get("/rwa/assets")

    # ------------------------------------------------------------------
    # Scanner
    # ------------------------------------------------------------------

    async def scan_protocol(
        self,
        protocol: str,
        contract_address: Optional[str] = None,
        chain: str = "casper",
    ) -> Dict[str, Any]:
        """Run a deep vulnerability scan on a protocol."""
        return await self._post(
            "/scanner/scan",
            {
                "protocol": protocol,
                "contract_address": contract_address,
                "chain": chain,
            },
        )

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    async def list_policies(self) -> Dict[str, Any]:
        """Return all active risk policies."""
        return await self._get("/policy/list")

    async def update_policy(
        self,
        policy_id: str,
        max_tvl_drop_pct: float,
        min_liquidity_ratio: float,
        alert_threshold: int,
    ) -> Dict[str, Any]:
        """Update a risk policy on-chain."""
        return await self._post(
            "/policy/update",
            {
                "policy_id": policy_id,
                "max_tvl_drop_pct": max_tvl_drop_pct,
                "min_liquidity_ratio": min_liquidity_ratio,
                "alert_threshold": alert_threshold,
            },
        )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    async def get_audit_log(self, limit: int = 50) -> Dict[str, Any]:
        """Fetch the on-chain audit log."""
        return await self._get("/audit/log", limit=limit)

    # ------------------------------------------------------------------
    # Chain
    # ------------------------------------------------------------------

    async def get_block_height(self) -> Dict[str, Any]:
        """Return current Casper block height."""
        return await self._get("/chain/block")

    # ------------------------------------------------------------------
    # Convenience: synchronous wrappers
    # ------------------------------------------------------------------

    def query_risk_sync(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper around :meth:`query_risk`."""
        return asyncio.run(self.query_risk(query, **kwargs))

    def detect_anomaly_sync(self, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper around :meth:`detect_anomaly`."""
        return asyncio.run(self.detect_anomaly(**kwargs))

    def scan_protocol_sync(self, protocol: str, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper around :meth:`scan_protocol`."""
        return asyncio.run(self.scan_protocol(protocol, **kwargs))
