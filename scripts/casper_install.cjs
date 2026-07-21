#!/usr/bin/env node
/**
 * VaultWatch — Casper-native Fresh Contract Install Helper (Node.js)
 *
 * Installs a contract as a NEW, UPGRADABLE contract package using Odra's
 * `install_new_contract()` path (which calls `storage::new_contract()` +
 * creates the `upgrader_group`). This is the v1 install that precedes a
 * Casper-native `add_contract_version()` upgrade.
 *
 * Uses the OFFICIAL `casper-js-sdk` v5 (sanctioned by docs.cspr.cloud) for
 * Casper-2.x-compatible deploy signing.
 *
 * Usage:
 *   node scripts/casper_install.cjs <request.json>
 *
 * request.json schema:
 *   {
 *     "key_path": "secret_key.pem",
 *     "wasm_path": "contracts/wasm/RiskPolicyManager.wasm",
 *     "payment_motes": 150000000000,
 *     "package_hash_key_name": "risk_policy_manager_package_hash",
 *     "rpc_url": "https://node.testnet.casper.network/rpc"
 *   }
 *
 * Output (JSON on stdout):
 *   { "success": true, "deploy_hash": "...", "block_hash": "...",
 *     "cost_motes": "...", "link": "...",
 *     "deployer_account_hash": "...", "error": null }
 *
 * After a successful install, the caller queries the deployer account's named
 * keys (via query_global_state) to resolve the freshly-created package hash
 * (stored under `package_hash_key_name`) and then resolves the v1 contract
 * hash + state URef from the package.
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
// Direct JSON-RPC helpers
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
// Core: build, sign, submit, verify the fresh-install session deploy
// ---------------------------------------------------------------------------

async function executeInstall(request) {
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

  // Compute the deployer's account hash (for proof / debugging)
  const accountHashBytes = publicKey.accountHash().hashBytes;
  const deployerAccountHash =
    'account-hash-' +
    Array.from(accountHashBytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

  // 2. Load Wasm
  const wasmPath = path.resolve(request.wasm_path);
  const wasmBytes = fs.readFileSync(wasmPath);
  if (process.env.DEBUG) {
    process.stderr.write(
      `[casper_install] wasm=${wasmPath} (${wasmBytes.length} bytes) deployer=${deployerAccountHash}\n`
    );
  }

  // 3. Build the Odra install runtime args.
  //    These mirror the constants in odra-core::consts (odra_cfg_*).
  //    odra_cfg_is_upgrade=false routes Odra's generated `call()` to
  //    install_new_contract(), which calls storage::new_contract()
  //    (creates the package + access URef) and provision_contract_user_group_uref
  //    (creates the upgrader_group).
  const packageHashKeyName = request.package_hash_key_name;

  const argsMap = {
    // Fresh install (NOT an upgrade).
    odra_cfg_is_upgrade: CLValue.newCLValueBool(false),
    // Make the package upgradable (creates the upgrader_group, enables
    // add_contract_version later).
    odra_cfg_is_upgradable: CLValue.newCLValueBool(true),
    // Named key under which the package hash is stored on the deployer account.
    odra_cfg_package_hash_key_name: CLValue.newCLString(packageHashKeyName),
    // Allow overwriting an existing named key (harmless on fresh install).
    odra_cfg_allow_key_override: CLValue.newCLValueBool(true),
    // Create the upgrader_group (required for the package to be upgradable).
    odra_cfg_create_upgrade_group: CLValue.newCLValueBool(true),
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
    process.stderr.write(`[casper_install] built+signed install deploy ${deployHash}\n`);
  }

  // 6. Submit via account_put_deploy
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
    process.stderr.write(`[casper_install] submitted ${returnedHash}\n`);
  }

  // 7. Verify on-chain execution (Casper 2.x Version2 format).
  const deadline = Date.now() + 240000; // 4 min
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
// Main
// ---------------------------------------------------------------------------

async function main() {
  if (process.argv.length < 3) {
    process.stderr.write('Usage: node scripts/casper_install.cjs <request.json>\n');
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
    const result = await executeInstall(request);
    console.log(JSON.stringify(result));
    process.exit(result.success ? 0 : 1);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: e.message }));
    process.exit(1);
  }
}

main();
