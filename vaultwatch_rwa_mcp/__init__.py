"""vaultwatch-rwa-mcp — domain-specific MCP server for the VaultWatch RWA contracts.

Exposes the 8 Casper testnet RWA / risk contracts (AuditTrail, RiskOracle,
RiskPolicyManager, SentinelAlertLog, SentinelCredit, SentinelRegistry,
SubscriberVault, AgentBehaviorIndex) to any LLM agent via the Model Context
Protocol.

Quickstart
----------
Run the MCP server over stdio (the standard MCP transport):

    python -m vaultwatch_rwa_mcp.server

Or via the npm launcher:

    npx vaultwatch-rwa-mcp

Connect from Claude Desktop / Cursor / Continue:

    {
      "mcpServers": {
        "vaultwatch-rwa": {
          "command": "python",
          "args": ["-m", "vaultwatch_rwa_mcp.server"]
        }
      }
    }

Reads are free ``query_global_state`` JSON-RPC calls. Writes are REAL deploys
signed via the CSPR.click AI Agent Skill (``agents.agent_wallet.AgentWallet`` →
``casper-js-sdk`` v5).
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
