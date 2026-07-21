#!/usr/bin/env node
/**
 * VaultWatch — Official Casper Deploy Helper (Node.js)
 *
 * Uses the OFFICIAL `casper-js-sdk` v5 (sanctioned by docs.cspr.cloud) to:
 *   1. Build a stored-contract-call deploy via ContractCallBuilder.buildFor1_5()
 *   2. Sign it with the deployer's SECP256K1 private key (PEM)
 *   3. Submit to the Casper Testnet via CSPR.cloud RPC (official middleware)
 *   4. Verify on-chain execution using direct JSON-RPC (account_put_deploy / info_get_deploy)
 *
 * Invoked by scripts/broadcast_interactions.py so the user-facing command remains:
 *     python3 scripts/broadcast_interactions.py
 *
 * Usage:
 *   node scripts/casper_deploy.cjs <request.json>
 *
 * request.json schema:
 *   {
 *     "key_path": "secret_key.pem",
 *     "contract_hash": "cd1579...",        // 64 hex chars, no prefix
 *     "entry_point": "record_finding",
 *     "payment_motes": 5000000000,
 *     "args": [ ["name", "String", "value"], ["n", "U8", 92], ... ],
 *     "rpc_url": "https://node.testnet.cspr.cloud/rpc",
 *     "auth_token": "019ef63a-..."
 *   }
 *
 * Output (JSON on stdout):
 *   { "success": true, "deploy_hash": "...", "block_hash": "...", "cost_motes": "...", "link": "...", "error": null }
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
// Public node does strict validation (rejects invalid signatures immediately)
// and reliably executes deploys. CSPR.cloud is the official middleware fallback.
const DEFAULT_RPC = 'https://node.testnet.casper.network/rpc';

// ---------------------------------------------------------------------------
// Direct JSON-RPC helpers (more reliable than the SDK's high-level wrappers
// for the verification step, which has stricter type expectations)
// ---------------------------------------------------------------------------

function rpcPost(rpcUrl, authToken, method, params) {
  const body = JSON.stringify({ jsonrpc: '2.0', id: 1, method, params });
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = authToken;

  return fetch(rpcUrl, {
    method: 'POST',
    headers,
    body,
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) throw new Error(`RPC ${method}: ${JSON.stringify(data.error)}`);
      return data.result;
    });
}

// ---------------------------------------------------------------------------
// CLValue builders
// ---------------------------------------------------------------------------

function buildArg(type, value) {
  switch (type) {
    case 'String':
      return CLValue.newCLString(String(value));
    case 'Bool':
      return CLValue.newCLValueBool(Boolean(value));
    case 'U8':
      return CLValue.newCLUint8(Number(value));
    case 'U32':
      return CLValue.newCLUInt32(Number(value));
    case 'I32':
      return CLValue.newCLInt32(Number(value));
    case 'U64':
      return CLValue.newCLUint64(String(value));
    case 'I64':
      return CLValue.newCLInt64(String(value));
    case 'U512':
      return CLValue.newCLUInt512(String(value));
    default:
      throw new Error(`Unsupported CL type: ${type}`);
  }
}

function buildArgs(argSpecs) {
  const map = {};
  for (const [name, type, value] of argSpecs) {
    map[name] = buildArg(type, value);
  }
  return Args.fromMap(map);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Core
// ---------------------------------------------------------------------------

async function executeDeploy(request) {
  const rpcUrl = request.rpc_url || DEFAULT_RPC;
  const authToken = request.auth_token || '';

  // 1. Load private key (SECP256K1)
  const keyPath = path.resolve(request.key_path);
  const pemContent = fs.readFileSync(keyPath, 'utf8');
  const keyAlgo =
    request.key_algorithm === 'ED25519'
      ? KeyAlgorithm.ED25519
      : KeyAlgorithm.SECP256K1;
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const publicKey = privateKey.publicKey;

  // 2. Build the contract-call deploy (V1 / Casper 1.5 format — universally
  //    accepted by account_put_deploy on both Casper 1.x and 2.x nodes)
  const runtimeArgs = buildArgs(request.args);

  const transaction = new ContractCallBuilder()
    .from(publicKey)
    .byHash(request.contract_hash)
    .entryPoint(request.entry_point)
    .runtimeArgs(runtimeArgs)
    .payment(request.payment_motes)
    .chainName(CHAIN_NAME)
    .buildFor1_5();

  // 3. Sign
  transaction.sign(privateKey);

  // 4. Serialize to the JSON the RPC expects
  const deployJson = transaction.toJSON();
  if (process.env.DEBUG) {
    const dh =
      (deployJson && (deployJson.hash || (deployJson.deploy && deployJson.deploy.hash))) ||
      'unknown';
    process.stderr.write(`[casper_deploy] built+signed deploy ${dh}\n`);
  }

  // 5. Submit via account_put_deploy (direct RPC)
  const submitResult = await rpcPost(rpcUrl, authToken, 'account_put_deploy', {
    deploy: deployJson,
  });
  const deployHash = submitResult.deploy_hash || submitResult.deployHash;
  if (!deployHash) {
    throw new Error(
      `submit succeeded but no deploy_hash returned: ${JSON.stringify(submitResult)}`
    );
  }
  if (process.env.DEBUG) {
    process.stderr.write(`[casper_deploy] submitted ${deployHash}\n`);
  }

  // 6. Verify on-chain execution (poll info_get_deploy).
  //    Casper 2.x response format: result.execution_info.execution_result.Version2
  //    { error_message: null }  => SUCCESS
  //    { error_message: "..." } => FAILURE
  const deadline = Date.now() + 180000;
  let lastError = null;
  while (Date.now() < deadline) {
    await sleep(8000);
    try {
      const result = await rpcPost(rpcUrl, authToken, 'info_get_deploy', {
        deploy_hash: deployHash,
      });
      const execInfo = result.execution_info;
      if (execInfo) {
        const blockHash = execInfo.block_hash || '';
        const execResult = execInfo.execution_result || {};
        // Casper 2.x wraps in Version2; Casper 1.x uses Success/Failure directly
        const v2 = execResult.Version2;
        if (v2) {
          const success = v2.error_message === null || v2.error_message === undefined;
          return {
            success,
            deploy_hash: deployHash,
            block_hash: blockHash,
            cost_motes: String(v2.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${deployHash}`,
            error: success ? null : v2.error_message,
          };
        }
        // Fallback: Casper 1.x format
        if (execResult.Success) {
          return {
            success: true,
            deploy_hash: deployHash,
            block_hash: blockHash,
            cost_motes: String(execResult.Success.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${deployHash}`,
            error: null,
          };
        } else if (execResult.Failure) {
          return {
            success: false,
            deploy_hash: deployHash,
            block_hash: blockHash,
            cost_motes: '0',
            link: `https://testnet.cspr.live/deploy/${deployHash}`,
            error: execResult.Failure.error_message || JSON.stringify(execResult.Failure),
          };
        }
      }
    } catch (e) {
      lastError = e.message;
    }
  }

  return {
    success: false,
    deploy_hash: deployHash,
    block_hash: '',
    cost_motes: '0',
    link: `https://testnet.cspr.live/deploy/${deployHash}`,
    error: `verification timeout (last poll error: ${lastError || 'none'})`,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  if (process.argv.length < 3) {
    process.stderr.write('Usage: node scripts/casper_deploy.cjs <request.json>\n');
    process.exit(2);
  }
  const requestFile = process.argv[2];
  let request;
  try {
    request = JSON.parse(fs.readFileSync(requestFile, 'utf8'));
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: `bad request file: ${e.message}` }));
    process.exit(1);
  }
  try {
    const result = await executeDeploy(request);
    console.log(JSON.stringify(result));
    process.exit(result.success ? 0 : 1);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: e.message }));
    process.exit(1);
  }
}

main();
