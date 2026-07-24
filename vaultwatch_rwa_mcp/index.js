#!/usr/bin/env node
/**
 * vaultwatch-rwa-mcp — Node.js launcher for the Python FastMCP server.
 *
 * Mirrors the pattern used by the sibling `vaultwatch_mcp` package
 * (casper-sentinel-mcp): a thin Node wrapper that spawns `python3 -m
 * vaultwatch_rwa_mcp.server` with inherited stdio, so any MCP client that
 * expects a Node-style command (Claude Desktop, Cursor, Continue) can launch
 * the Python server transparently via `npx vaultwatch-rwa-mcp`.
 *
 * The Python server speaks the Model Context Protocol over stdio (JSON-RPC).
 * Node just passes stdin/stdout through unchanged.
 */

'use strict';

const { spawn } = require('child_process');
const path = require('path');

// Prefer python3, fall back to python. The MCP stdio protocol is binary-safe
// over stdin/stdout, so we inherit stdio without any re-encoding.
const PYTHON = process.env.VAULTWATCH_RWA_MCP_PYTHON || 'python3';

const child = spawn(
  PYTHON,
  ['-m', 'vaultwatch_rwa_mcp.server'],
  {
    cwd: path.resolve(__dirname),
    stdio: 'inherit',
    env: { ...process.env },
  }
);

child.on('error', (err) => {
  process.stderr.write(`vaultwatch-rwa-mcp: failed to spawn ${PYTHON}: ${err.message}\n`);
  process.stderr.write(`  Set VAULTWATCH_RWA_MCP_PYTHON to your python interpreter if needed.\n`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.exit(128 + 15); // SIGTERM
  }
  process.exit(code || 0);
});
