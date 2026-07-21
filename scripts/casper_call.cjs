#!/usr/bin/env node
/**
 * VaultWatch — Generic Casper Stored-Contract Call Helper (Node.js)
 *
 * Builds, signs, submits, and on-chain verifies a REAL stored-contract deploy
 * (StoredVersionedContractByHash / ContractCallBuilder) calling ANY entry point
 * on ANY deployed VaultWatch contract. This is the single Node.js helper that
 * the Python MCP server shells out to for WRITE operations — because pycspr
 * (Python) produces signatures incompatible with Casper 2.x (see worklog
 * Task 1), ALL real deploys MUST go through casper-js-sdk (Node.js).
 *
 * Uses the OFFICIAL `casper-js-sdk` v5 (sanctioned by docs.cspr.cloud) for
 * Casper-2.x-compatible deploy signing — the same SDK + ContractCallBuilder
 * pattern that produced the 21 verified-success interaction deploys and the
 * x402 open_vault payment (see proof/PROOF.md §8 + §11).
 *
 * Usage:
 *   echo '<request.json>' | node scripts/casper_call.cjs
 *   node scripts/casper_call.cjs <request.json>
 *
 * request.json schema:
 *   {
 *     "contract_hash": "<64-hex-char contract hash WITHOUT 'hash-' prefix>",
 *     "entry_point": "record_decision",
 *     "args": {
 *       "agent_name":     { "type": "string", "value": "AnomalyAgent" },
 *       "confidence":     { "type": "u8",     "value": "91" },
 *       "correction":     { "type": "bool",   "value": false },
 *       "block_height":   { "type": "u64",    "value": "1500000" }
 *     },
 *     "payment_motes": 5000000000,         // optional, default 5 CSPR
 *     "signer_pem_path": "secret_key.pem",  // optional, default ./secret_key.pem
 *     "key_algorithm": "secp256k1",         // optional, default secp256k1
 *     "rpc_url": "https://node.testnet.casper.network/rpc",  // optional
 *     "verify_timeout_ms": 240000           // optional, default 240s
 *   }
 *
 * Output (JSON on stdout):
 *   { "success": true,
 *     "deploy_hash": "...", "block_hash": "...",
 *     "cost_motes": "...", "link": "https://testnet.cspr.live/deploy/...",
 *     "deployer_account_hash": "account-hash-...",
 *     "error": null }
 *
 * Supported CL types (per casper-js-sdk v5 CLValue API):
 *   string → CLValue.newCLString
 *   bool   → CLValue.newCLValueBool
 *   u8     → CLValue.newCLUint8        (lowercase 'u' in 'int' — SDK quirk)
 *   u64    → CLValue.newCLUint64       (lowercase 'u' in 'int' — SDK quirk)
 *   u512   → CLValue.newCLUInt512      (capital 'U' — SDK quirk)
 *   u32    → CLValue.newCLUInt32
 *   i32    → CLValue.newCLInt32
 *   i64    → CLValue.newCLInt64
 */

'use strict';

const fs = require('fs');
const path = require('path');
const {
  PrivateKey,
  KeyAlgorithm,
  Args,
  CLValue,
  ContractCallBuilder,
} = require('casper-js-sdk');

const CHAIN_NAME = 'casper-test';
const DEFAULT_RPC = 'https://node.testnet.casper.network/rpc';
const DEFAULT_PAYMENT_MOTES = 5_000_000_000; // 5 CSPR
const DEFAULT_VERIFY_TIMEOUT_MS = 240_000; // 4 min

// ---------------------------------------------------------------------------
// Direct JSON-RPC helpers (same pattern as casper_install.cjs)
// ---------------------------------------------------------------------------

function rpcPost(rpcUrl, method, params) {
  const body = JSON.stringify({ jsonrpc: '2.0', id: 1, method, params });
  return fetch(rpcUrl, {
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Build a single CLValue from a { type, value } descriptor
// ---------------------------------------------------------------------------

function buildCLValue(type, value) {
  // Normalize the type string (accept both "u8"/"U8", "u512"/"U512", etc.)
  const t = String(type).toLowerCase();
  const v = String(value);

  switch (t) {
    case 'string':
    case 'str':
      return CLValue.newCLString(v);
    case 'bool':
    case 'boolean':
      return CLValue.newCLValueBool(v === true || v === 'true');
    case 'u8':
      return CLValue.newCLUint8(v);
    case 'u64':
      return CLValue.newCLUint64(v);
    case 'u512':
      return CLValue.newCLUInt512(v);
    case 'u32':
      return CLValue.newCLUInt32(v);
    case 'i32':
    case 'int32':
      return CLValue.newCLInt32(v);
    case 'i64':
    case 'int64':
      return CLValue.newCLInt64(v);
    default:
      throw new Error(`Unsupported CL type: ${type} (supported: string, bool, u8, u64, u512, u32, i32, i64)`);
  }
}

// ---------------------------------------------------------------------------
// Core: build, sign, submit, verify a stored-contract deploy
// ---------------------------------------------------------------------------

async function executeCall(request) {
  const rpcUrl = request.rpc_url || DEFAULT_RPC;
  const contractHash = request.contract_hash;
  const entryPoint = request.entry_point;
  const typedArgs = request.args || {};

  if (!contractHash) throw new Error('contract_hash is required');
  if (!entryPoint) throw new Error('entry_point is required');

  // 1. Load deployer private key
  const pemPath = request.signer_pem_path || path.resolve('secret_key.pem');
  const pemContent = request.signer_pem || fs.readFileSync(pemPath, 'utf8');
  const keyAlgo =
    (request.key_algorithm || 'secp256k1').toLowerCase() === 'ed25519'
      ? KeyAlgorithm.ED25519
      : KeyAlgorithm.SECP256K1;
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const publicKey = privateKey.publicKey;

  // Compute the deployer's account hash (for proof / debugging)
  const accountHashBytes = publicKey.accountHash().hashBytes;
  const deployerAccountHash =
    'account-hash-' +
    Array.from(accountHashBytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

  // 2. Build runtime args from the typed-args dict
  const argsMap = {};
  for (const [name, desc] of Object.entries(typedArgs)) {
    // Accept both { type, value } and a shorthand scalar (string)
    if (typeof desc === 'object' && desc !== null && 'type' in desc) {
      argsMap[name] = buildCLValue(desc.type, desc.value);
    } else {
      // Shorthand: treat as string
      argsMap[name] = CLValue.newCLString(String(desc));
    }
  }
  const runtimeArgs = Args.fromMap(argsMap);

  if (process.env.DEBUG) {
    process.stderr.write(
      `[casper_call] contract=${contractHash} entry_point=${entryPoint} ` +
        `args=${JSON.stringify(Object.keys(typedArgs))} deployer=${deployerAccountHash}\n`
    );
  }

  // 3. Build the stored-contract-call deploy via ContractCallBuilder
  //    (same builder that produced the 21 verified-success deploys + the
  //     x402 open_vault payment — see proof/PROOF.md §8 + §11).
  //    .byHash() takes the 64-hex contract hash (with or without 'hash-' prefix).
  const transaction = new ContractCallBuilder()
    .from(publicKey)
    .byHash(contractHash)
    .entryPoint(entryPoint)
    .runtimeArgs(runtimeArgs)
    .payment(String(request.payment_motes || DEFAULT_PAYMENT_MOTES))
    .chainName(CHAIN_NAME)
    .buildFor1_5();

  // 4. Sign
  transaction.sign(privateKey);

  const deployJson = transaction.toJSON();
  const deployHash =
    (deployJson && (deployJson.hash || (deployJson.deploy && deployJson.deploy.hash))) ||
    'unknown';

  if (process.env.DEBUG) {
    process.stderr.write(`[casper_call] built+signed deploy ${deployHash}\n`);
  }

  // 5. Submit via account_put_deploy
  const submitResult = await rpcPost(rpcUrl, 'account_put_deploy', {
    deploy: deployJson,
  });
  const returnedHash = submitResult.deploy_hash || submitResult.deployHash;
  if (!returnedHash) {
    throw new Error(
      `submit succeeded but no deploy_hash returned: ${JSON.stringify(submitResult)}`
    );
  }
  if (process.env.DEBUG) {
    process.stderr.write(`[casper_call] submitted ${returnedHash}\n`);
  }

  // 6. Verify on-chain execution (Casper 2.x Version2 format)
  const deadline = Date.now() + (request.verify_timeout_ms || DEFAULT_VERIFY_TIMEOUT_MS);
  let lastError = null;
  while (Date.now() < deadline) {
    await sleep(8000);
    try {
      const result = await rpcPost(rpcUrl, 'info_get_deploy', {
        deploy_hash: returnedHash,
      });
      const execInfo = result.execution_info;
      if (execInfo) {
        const blockHash = execInfo.block_hash || '';
        const execResult = execInfo.execution_result || {};
        const v2 = execResult.Version2;
        if (v2) {
          const success =
            v2.error_message === null || v2.error_message === undefined;
          return {
            success,
            deploy_hash: returnedHash,
            block_hash: blockHash,
            cost_motes: String(v2.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${returnedHash}`,
            deployer_account_hash: deployerAccountHash,
            error: success ? null : v2.error_message,
          };
        }
        // Casper 1.x fallback
        if (execResult.Success) {
          return {
            success: true,
            deploy_hash: returnedHash,
            block_hash: blockHash,
            cost_motes: String(execResult.Success.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${returnedHash}`,
            deployer_account_hash: deployerAccountHash,
            error: null,
          };
        } else if (execResult.Failure) {
          return {
            success: false,
            deploy_hash: returnedHash,
            block_hash: blockHash,
            cost_motes: '0',
            link: `https://testnet.cspr.live/deploy/${returnedHash}`,
            deployer_account_hash: deployerAccountHash,
            error:
              execResult.Failure.error_message ||
              JSON.stringify(execResult.Failure),
          };
        }
      }
    } catch (e) {
      lastError = e.message;
    }
  }

  return {
    success: false,
    deploy_hash: returnedHash,
    block_hash: '',
    cost_motes: '0',
    link: `https://testnet.cspr.live/deploy/${returnedHash}`,
    deployer_account_hash: deployerAccountHash,
    error: `verification timeout (last poll error: ${lastError || 'none'})`,
  };
}

// ---------------------------------------------------------------------------
// Main — read request from stdin or file arg, write result to stdout
// ---------------------------------------------------------------------------

async function main() {
  let request;
  try {
    if (process.argv.length >= 3 && process.argv[2] !== '-') {
      // File argument
      request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    } else {
      // Read from stdin
      const chunks = [];
      for await (const chunk of process.stdin) {
        chunks.push(chunk);
      }
      const stdinStr = Buffer.concat(chunks).toString('utf8').trim();
      if (!stdinStr) {
        process.stderr.write('Usage: echo "<request.json>" | node scripts/casper_call.cjs\n');
        process.stderr.write('   or: node scripts/casper_call.cjs <request.json>\n');
        process.exit(2);
      }
      request = JSON.parse(stdinStr);
    }
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: `bad request JSON: ${e.message}` }));
    process.exit(1);
  }
  try {
    const result = await executeCall(request);
    console.log(JSON.stringify(result));
    process.exit(result.success ? 0 : 1);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: e.message }));
    process.exit(1);
  }
}

main();
