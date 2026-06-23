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

    async def __aenter__(self) -> "VaultWatchClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
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
                headers={"Authorization": f"Bearer {self.api_key}"}
                if self.api_key
                else {},
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
