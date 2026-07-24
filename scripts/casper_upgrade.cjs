#!/usr/bin/env node
/**
 * VaultWatch — Casper-native Contract Upgrade Helper (Node.js)
 *
 * Installs a v2 contract as a NEW VERSION under an EXISTING contract package
 * using the Casper host function `storage::add_contract_version(...)`. The
 * upgrade is triggered the Casper-native way: deploy the v2 Wasm as session
 * code (ModuleBytes) with the Odra runtime arg `odra_cfg_is_upgrade=true` and
 * `odra_cfg_package_hash_to_upgrade=<v1 package hash>`. Odra's generated
 * `call()` entry point then invokes `storage::add_contract_version()` on-chain.
 *
 * Uses the OFFICIAL `casper-js-sdk` v5 (sanctioned by docs.cspr.cloud), which
 * produces Casper-2.x-compatible signatures (unlike pycspr, whose deploys are
 * silently dropped by Casper 2.x nodes).
 *
 * Usage:
 *   node scripts/casper_upgrade.cjs <request.json>
 *
 * request.json schema:
 *   {
 *     "key_path": "secret_key.pem",
 *     "wasm_path": "contracts/wasm/RiskPolicyManagerV2.wasm",
 *     "payment_motes": 100000000000,
 *     "package_hash": "aaf7f48d...7b2c4",          // 64 hex chars, v1 package hash
 *     "package_hash_key_name": "risk_policy_manager_package_hash",
 *     "rpc_url": "https://node.testnet.casper.network/rpc"
 *   }
 *
 * Output (JSON on stdout):
 *   { "success": true, "deploy_hash": "...", "block_hash": "...",
 *     "cost_motes": "...", "link": "...", "error": null }
 */

'use strict';

const fs = require('fs');
const path = require('path');
const {
  PrivateKey,
  KeyAlgorithm,
  Args,
  CLValue,
  SessionBuilder,
} = require('casper-js-sdk');

const CHAIN_NAME = 'casper-test';
const DEFAULT_RPC = 'https://node.testnet.casper.network/rpc';

// ---------------------------------------------------------------------------
// Direct JSON-RPC helpers (mirrors scripts/casper_deploy.cjs)
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
// Core: build, sign, submit, verify the upgrade session deploy
// ---------------------------------------------------------------------------

async function executeUpgrade(request) {
  const rpcUrl = request.rpc_url || DEFAULT_RPC;

  // 1. Load deployer private key (SECP256K1)
  const keyPath = path.resolve(request.key_path);
  const pemContent = fs.readFileSync(keyPath, 'utf8');
  const keyAlgo =
    request.key_algorithm === 'ED25519'
      ? KeyAlgorithm.ED25519
      : KeyAlgorithm.SECP256K1;
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const publicKey = privateKey.publicKey;

  // 2. Load v2 Wasm
  const wasmPath = path.resolve(request.wasm_path);
  const wasmBytes = fs.readFileSync(wasmPath);
  if (process.env.DEBUG) {
    process.stderr.write(
      `[casper_upgrade] wasm=${wasmPath} (${wasmBytes.length} bytes)\n`
    );
  }

  // 3. Build the Odra upgrade runtime args.
  //    These mirror the constants in odra-core::consts (odra_cfg_*).
  //    odra_cfg_package_hash_to_upgrade is a HashAddr = [u8; 32] -> CLType ByteArray(32).
  const packageHashHex = String(request.package_hash).replace(/^0x/, '');
  if (packageHashHex.length !== 64) {
    throw new Error(
      `package_hash must be 64 hex chars (32 bytes), got ${packageHashHex.length}`
    );
  }
  const packageHashBytes = Uint8Array.from(
    packageHashHex.match(/.{2}/g).map((h) => parseInt(h, 16))
  );

  const argsMap = {
    // Trigger the upgrade path in Odra's generated `call()`.
    odra_cfg_is_upgrade: CLValue.newCLValueBool(true),
    // The v1 package hash to add a new version to (32 raw bytes).
    odra_cfg_package_hash_to_upgrade: CLValue.newCLByteArray(packageHashBytes),
    // Named key under which the package hash is stored on the deployer account.
    odra_cfg_package_hash_key_name: CLValue.newCLString(
      request.package_hash_key_name
    ),
    // Allow re-storing the package hash key (it already exists from v1 install).
    odra_cfg_allow_key_override: CLValue.newCLValueBool(true),
    // Do NOT recreate the upgrader user group — v1's install already created
    // "upgrader_group", and re-creating it raises GroupAlreadyExists
    // (ApiError::ContractHeader(3)). Set false so Odra skips group creation.
    odra_cfg_create_upgrade_group: CLValue.newCLValueBool(false),
    // Keep the package upgradable (matches v1 install config).
    odra_cfg_is_upgradable: CLValue.newCLValueBool(true),
  };
  const runtimeArgs = Args.fromMap(argsMap);

  // 4. Build the ModuleBytes session deploy (installOrUpgrade mode).
  const transaction = new SessionBuilder()
    .from(publicKey)
    .wasm(wasmBytes)
    .installOrUpgrade()
    .runtimeArgs(runtimeArgs)
    .payment(String(request.payment_motes))
    .chainName(CHAIN_NAME)
    .buildFor1_5();

  // 5. Sign
  transaction.sign(privateKey);

  const deployJson = transaction.toJSON();
  const deployHash =
    (deployJson && (deployJson.hash || (deployJson.deploy && deployJson.deploy.hash))) ||
    'unknown';
  if (process.env.DEBUG) {
    process.stderr.write(`[casper_upgrade] built+signed upgrade deploy ${deployHash}\n`);
  }

  // 6. Submit via account_put_deploy — OR, if SPECULATIVE=1, run speculative_exec
  //    instead (executes the deploy without committing, returns the gas estimate;
  //    spends NO CSPR). Used to size the payment before the real attempt.
  if (process.env.SPECULATIVE === '1') {
    let specResult;
    try {
      specResult = await rpcPost(rpcUrl, 'speculative_exec', { deploy: deployJson });
    } catch (e) {
      return {
        success: false,
        deploy_hash: deployHash,
        block_hash: '',
        cost_motes: '0',
        link: `https://testnet.cspr.live/deploy/${deployHash}`,
        error: `speculative_exec failed: ${e.message}`,
      };
    }
    // speculative_exec response: result.execution_effects + result.execution_result
    const er = specResult.execution_result || {};
    const v2 = er.Version2 || {};
    const success = v2.error_message === null || v2.error_message === undefined;
    return {
      success,
      deploy_hash: deployHash,
      block_hash: specResult.block_hash || '',
      cost_motes: String(v2.cost || '0'),
      link: `https://testnet.cspr.live/deploy/${deployHash}`,
      error: success ? null : `speculative: ${v2.error_message}`,
      speculative: true,
    };
  }

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
    process.stderr.write(`[casper_upgrade] submitted ${returnedHash}\n`);
  }

  // 7. Verify on-chain execution. Casper 2.x:
  //    result.execution_info.execution_result.Version2 { error_message: null } => SUCCESS
  const deadline = Date.now() + 240000; // 4 min (upgrades are heavier)
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
            error: null,
          };
        } else if (execResult.Failure) {
          return {
            success: false,
            deploy_hash: returnedHash,
            block_hash: blockHash,
            cost_motes: '0',
            link: `https://testnet.cspr.live/deploy/${returnedHash}`,
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
    error: `verification timeout (last poll error: ${lastError || 'none'})`,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  if (process.argv.length < 3) {
    process.stderr.write('Usage: node scripts/casper_upgrade.cjs <request.json>\n');
    process.exit(2);
  }
  let request;
  try {
    request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: `bad request file: ${e.message}` }));
    process.exit(1);
  }
  try {
    const result = await executeUpgrade(request);
    console.log(JSON.stringify(result));
    process.exit(result.success ? 0 : 1);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: e.message }));
    process.exit(1);
  }
}

main();
