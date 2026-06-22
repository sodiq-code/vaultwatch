"""
VaultWatch Python SDK
~~~~~~~~~~~~~~~~~~~~~

DeFi Risk Intelligence on Casper — official Python client.

Usage::

    from vaultwatch import VaultWatchClient

    client = VaultWatchClient(base_url="http://localhost:8000")
    result = await client.query_risk("Is Uniswap v3 safe right now?")
"""

from .client import VaultWatchClient

__version__ = "4.0.0"
__all__ = ["VaultWatchClient"]
