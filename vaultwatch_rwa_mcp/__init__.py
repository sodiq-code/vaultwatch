"""
VaultWatch RWA MCP Server — Compliance-Gated RWA Intelligence

5 RWA-specific MCP tools for Claude Desktop integration:
  1. rwa_risk_assessment   — Query RWA risk for a Casper address
  2. compliance_check      — Verify compliance requirements
  3. rwa_oracle_query      — Get RWA attestation data
  4. subscribe_rwa_feed    — x402-gated RWA subscription
  5. agent_reputation      — Query agent trust scores
"""

from . import server as server  # noqa: F401

__version__ = "1.0.0"
__all__ = ["server"]
