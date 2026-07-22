#!/usr/bin/env node
/**
 * VaultWatch — CSPR.click AI Agent Skill: Agent Wallet Helper (Node.js)
 *
 * Programmatic agent wallet CREATION + INFO — replaces manual key management.
 *
 * === Why this exists ========================================================
 * The CSPR.click AI Agent Skill (skills/csprclick-skill/SKILL.md) teaches AI
 * coding assistants how to integrate the CSPR.click Web SDK for browser-based
 * wallet operations. The Web SDK is browser-only — every signature requires
 * a human to approve in their wallet UI (Casper Wallet extension /
 * WalletConnect / social-login wallet).
 *
 * For headless / autonomous agent workflows (pytest e2e tests, MCP server
 * deploys, scheduled pipeline writes), the skill's reference implementation
 * (Autarca — https://github.com/AK-Bit-Lab/Autarca) uses the same
 * `casper-js-sdk` v5 that CSPR.click uses under the hood, but loads the
 * agent keypair from a server-side PEM file instead of a browser wallet.
 *
 * This helper implements that server-side agent-wallet pattern, with one
 * critical improvement over the prior "manual key management" approach:
 *
 *   ┌──────────────────────────────────────────────────────────────────────┐
 *   │  The agent keypair is CREATED PROGRAMMATICALLY via                  │
 *   │  `PrivateKey.generate(KeyAlgorithm.SECP256K1)` — no external        │
 *   │  keygen, no manually-imported .pem files, no committed secrets.     │
 *   │  The key lives at $VAULTWATCH_AGENT_KEY_PATH (default               │
 *   │  ~/.vaultwatch/agent_key.pem) which is gitignored.                  │
 *   │  On first run, the helper CREATES the key + prints the public key   │
 *   │  + the testnet faucet URL so the operator can fund it.              │
 *   └──────────────────────────────────────────────────────────────────────┘
 *
 * === Commands ===============================================================
 *   create    Generate a NEW SECP256K1 agent keypair, save to
 *             $VAULTWATCH_AGENT_KEY_PATH, print public_key + account_hash +
 *             faucet URL. Refuses to overwrite an existing key unless
 *             `--force` is passed.
 *   info      Load the existing agent keypair, print public_key + account_hash
 *             + CSPR balance (queried from RPC).
 *   public    Print ONLY the agent's public key (hex, no prefix). Useful for
 *             CI scripts that need to assert the wallet is funded.
 *
 * === Usage ==================================================================
 *   node scripts/csprclick_agent_wallet.cjs create [--force]
 *   node scripts/csprclick_agent_wallet.cjs info
 *   node scripts/csprclick_agent_wallet.cjs public
 *
 * === Environment ============================================================
 *   VAULTWATCH_AGENT_KEY_PATH  Path to agent key PEM
 *                              (default: ~/.vaultwatch/agent_key.pem)
 *   VAULTWATCH_AGENT_KEY_ALGO  secp256k1 | ed25519  (default: secp256k1)
 *   CASPER_RPC_URL             RPC endpoint
 *                              (default: https://node.testnet.casper.network/rpc)
 *   CASPER_CHAIN_NAME          Chain name (default: casper-test)
 *
 * === Output =================================================================
 *   JSON on stdout: { ok: true, command: "...", ... }
 *   On error:       { ok: false, error: "..." }  + exit code 1
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { PrivateKey, KeyAlgorithm } = require('casper-js-sdk');

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_RPC = 'https://node.testnet.casper.network/rpc';
const DEFAULT_CHAIN = 'casper-test';
const DEFAULT_KEY_ALGO = 'secp256k1';
const FAUCET_URL = 'https://testnet.cspr.live/tools/faucet';
const EXPLORER_ACCOUNT_URL = 'https://testnet.cspr.live/account/';

// CSPR = 1e9 motes
const MOTES_PER_CSPR = 1_000_000_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function agentKeyPath() {
  const p = process.env.VAULTWATCH_AGENT_KEY_PATH;
  if (p && p.trim()) return path.resolve(p);
  return path.join(os.homedir(), '.vaultwatch', 'agent_key.pem');
}

function keyAlgo() {
  const a = (process.env.VAULTWATCH_AGENT_KEY_ALGO || DEFAULT_KEY_ALGO).toLowerCase();
  if (a === 'ed25519' || a === 'ed') return KeyAlgorithm.ED25519;
  return KeyAlgorithm.SECP256K1;
}

function rpcUrl() {
  return process.env.CASPER_RPC_URL || DEFAULT_RPC;
}

function chainName() {
  return process.env.CASPER_CHAIN_NAME || DEFAULT_CHAIN;
}

function ensureDirFor(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
}

function publicKeyHex(publicKey) {
  // publicKey.toHex() returns '02...' (SECP256K1) or '01...' (ED25519) — 66 hex chars
  return publicKey.toHex();
}

function accountHashHex(publicKey) {
  const ahBytes = publicKey.accountHash().hashBytes;
  return 'account-hash-' + Array.from(ahBytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function rpcPost(url, method, params) {
  const body = JSON.stringify({ jsonrpc: '2.0', id: 1, method, params });
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) throw new Error(`RPC ${method}: ${JSON.stringify(data.error)}`);
      return data.result;
    });
}

async function getAccountBalance(rpcUrl, publicKeyHexStr) {
  // state_get_account_info returns the main_purse URef; then state_get_balance
  // returns the purse balance in motes.
  try {
    const acctResult = await rpcPost(rpcUrl, 'state_get_account_info', {
      public_key: publicKeyHexStr,
    });
    const purse = acctResult.account && acctResult.account.main_purse;
    if (!purse) return null;
    const srhResult = await rpcPost(rpcUrl, 'chain_get_state_root_hash', {});
    const srh = srhResult.state_root_hash;
    const balResult = await rpcPost(rpcUrl, 'state_get_balance', {
      state_root_hash: srh,
      purse_uref: purse,
    });
    const motes = parseInt(balResult.balance_value || '0', 10);
    return motes;
  } catch (e) {
    return null; // account may not exist yet (unfunded) — treat as 0 / unknown
  }
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

async function cmdCreate(args) {
  const force = args.includes('--force') || args.includes('-f');
  const keyPath = agentKeyPath();

  if (fs.existsSync(keyPath) && !force) {
    return {
      ok: false,
      error: `Refusing to overwrite existing agent key at ${keyPath}. Pass --force to overwrite.`,
    };
  }

  const algo = keyAlgo();
  const algoName = algo === KeyAlgorithm.ED25519 ? 'ed25519' : 'secp256k1';

  // Programmatic keypair generation — the heart of "agent wallet creation".
  // casper-js-sdk v5 PrivateKey.generate() uses Node's crypto.randomBytes
  // for the 32-byte seed.
  const privateKey = await PrivateKey.generate(algo);
  const publicKey = privateKey.publicKey;

  // Serialize to PEM (standard Casper PEM format: -----BEGIN PRIVATE KEY-----)
  // casper-js-sdk v5 exposes PrivateKey#toPem() (verified on the prototype).
  const pem = privateKey.toPem();

  ensureDirFor(keyPath);
  fs.writeFileSync(keyPath, pem, { mode: 0o600 });

  const pubHex = publicKeyHex(publicKey);
  const ahHex = accountHashHex(publicKey);

  return {
    ok: true,
    command: 'create',
    created: true,
    key_path: keyPath,
    key_algorithm: algoName,
    public_key: pubHex,
    account_hash: ahHex,
    chain_name: chainName(),
    rpc_url: rpcUrl(),
    faucet_url: FAUCET_URL,
    explorer_url: EXPLORER_ACCOUNT_URL + pubHex,
    next_step: `Fund this agent wallet at ${FAUCET_URL} (paste the public key above), then run \`node scripts/csprclick_agent_wallet.cjs info\` to verify the balance.`,
  };
}

async function cmdInfo() {
  const keyPath = agentKeyPath();
  if (!fs.existsSync(keyPath)) {
    return {
      ok: false,
      error: `No agent wallet found at ${keyPath}. Run \`node scripts/csprclick_agent_wallet.cjs create\` first.`,
    };
  }

  const algo = keyAlgo();
  const pemContent = fs.readFileSync(keyPath, 'utf8');
  const privateKey = await PrivateKey.fromPem(pemContent, algo);
  const publicKey = privateKey.publicKey;
  const pubHex = publicKeyHex(publicKey);
  const ahHex = accountHashHex(publicKey);

  const balanceMotes = await getAccountBalance(rpcUrl(), pubHex);
  const balanceCspr = balanceMotes === null ? null : balanceMotes / MOTES_PER_CSPR;

  return {
    ok: true,
    command: 'info',
    key_path: keyPath,
    key_algorithm: algo === KeyAlgorithm.ED25519 ? 'ed25519' : 'secp256k1',
    public_key: pubHex,
    account_hash: ahHex,
    chain_name: chainName(),
    rpc_url: rpcUrl(),
    balance_motes: balanceMotes,
    balance_cspr: balanceCspr,
    funded: balanceMotes !== null && balanceMotes > 0,
    explorer_url: EXPLORER_ACCOUNT_URL + pubHex,
    faucet_url: FAUCET_URL,
  };
}

async function cmdPublic() {
  const keyPath = agentKeyPath();
  if (!fs.existsSync(keyPath)) {
    return {
      ok: false,
      error: `No agent wallet found at ${keyPath}. Run \`node scripts/csprclick_agent_wallet.cjs create\` first.`,
    };
  }
  const algo = keyAlgo();
  const pemContent = fs.readFileSync(keyPath, 'utf8');
  const privateKey = await PrivateKey.fromPem(pemContent, algo);
  return {
    ok: true,
    command: 'public',
    public_key: privateKey.publicKey.toHex(),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const argv = process.argv.slice(2);
  const cmd = argv[0] || '';

  try {
    let result;
    switch (cmd) {
      case 'create':
        result = await cmdCreate(argv.slice(1));
        break;
      case 'info':
        result = await cmdInfo();
        break;
      case 'public':
        result = await cmdPublic();
        break;
      case '':
      case 'help':
      case '--help':
      case '-h':
        console.log(JSON.stringify({
          ok: true,
          command: 'help',
          usage: [
            'node scripts/csprclick_agent_wallet.cjs create [--force]',
            'node scripts/csprclick_agent_wallet.cjs info',
            'node scripts/csprclick_agent_wallet.cjs public',
          ],
          env: {
            VAULTWATCH_AGENT_KEY_PATH: '(default ~/.vaultwatch/agent_key.pem)',
            VAULTWATCH_AGENT_KEY_ALGO: 'secp256k1 | ed25519 (default secp256k1)',
            CASPER_RPC_URL: `(default ${DEFAULT_RPC})`,
            CASPER_CHAIN_NAME: `(default ${DEFAULT_CHAIN})`,
          },
        }, null, 2));
        process.exit(0);
        break;
      default:
        result = { ok: false, error: `Unknown command: ${cmd}. Try 'help'.` };
    }
    console.log(JSON.stringify(result, null, 2));
    process.exit(result.ok ? 0 : 1);
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: e.message, stack: e.stack }, null, 2));
    process.exit(1);
  }
}

main();
