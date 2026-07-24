#!/usr/bin/env node
/**
 * casper-sentinel-mcp
 * Launches the VaultWatch MCP server (Python/FastMCP) via stdio transport.
 * Claude Desktop config:
 * {
 *   "mcpServers": {
 *     "casper-sentinel": {
 *       "command": "npx",
 *       "args": ["casper-sentinel-mcp"]
 *     }
 *   }
 * }
 */

const { spawn } = require("child_process");
const path = require("path");

const serverPath = path.join(__dirname, "server.py");

const proc = spawn("python3", [serverPath], {
  stdio: "inherit",
  env: { ...process.env },
});

proc.on("error", (err) => {
  console.error("casper-sentinel-mcp: failed to start Python server:", err.message);
  console.error("Make sure Python 3.10+ and casper-sentinel are installed.");
  process.exit(1);
});

proc.on("exit", (code) => {
  process.exit(code ?? 0);
});
