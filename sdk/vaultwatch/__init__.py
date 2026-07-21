"""
VaultWatch Python SDK
~~~~~~~~~~~~~~~~~~~~~

DeFi Risk Intelligence on Casper — official Python client.

Usage::

    from vaultwatch import VaultWatchClient

    client = VaultWatchClient(base_url="http://localhost:8000")
    result = await client.query_risk("Is Uniswap v3 safe right now?")

    # Direct on-chain contract reads (via the FastAPI proxy):
    finding = await client.audit_trail.get_finding(1)
    score   = await client.risk_oracle.get_score("account-hash-abcdef...")
"""

from .client import (
    AuditTrailNamespace,
    RiskOracleNamespace,
    VaultWatchClient,
)

__version__ = "4.1.0"
__all__ = ["VaultWatchClient", "AuditTrailNamespace", "RiskOracleNamespace"]
