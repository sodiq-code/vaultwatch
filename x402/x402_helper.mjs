#!/usr/bin/env node
/**
 * VaultWatch — x402 Helper CLI (ESM)
 *
 * This is the bridge between the Python FastAPI server (api/main.py) and the
 * official @make-software/casper-x402 / @x402/core JavaScript SDKs.
 *
 * The Python server cannot use the Casper x402 SDK directly (no Python Casper
 * scheme exists — see docs/X402_INTEGRATION.md §12), so it shells out to this
 * helper for the four operations that require the JS SDK:
 *
 *   1. encode-payment-required  — build the x402 v2 PaymentRequired JSON +
 *                                 base64 PAYMENT-REQUIRED header value
 *   2. verify-payment-signature — decode + cryptographically verify a client's
 *                                 PAYMENT-SIGNATURE header (EIP-712 sig check
 *                                 via the official facilitator scheme)
 *   3. submit-vault-payment     — build, sign, submit, and on-chain verify a
 *                                 REAL SubscriberVault.open_vault() deploy on
 *                                 Casper testnet (the verified payment hash)
 *   4. build-settle-response    — build the x402 v2 SettleResponse +
 *                                 base64 PAYMENT-RESPONSE header value
 *
 * Why ESM (.mjs)?
 *   - `casper-js-sdk` v5 ships as CommonJS only (no ESM build — see its
 *     package.json `exports['.'].default = ./dist/lib.node.js`).
 *   - `@make-software/casper-x402`'s CJS build (dist/cjs/index.js) has a
 *     bundler-interop bug: it does `var { KeyAlgorithm } = import_default`
 *     which is `undefined` when `require()`'d against a CJS module.
 *   - The ESM build (dist/esm/index.mjs) of `@make-software/casper-x402`
 *     uses a different interop path that works correctly with `casper-js-sdk`
 *     via Node's CJS-namespace-interop.
 *   - Therefore we use an ESM `.mjs` file with `import * as casperSdk from
 *     'casper-js-sdk'` (namespace import) — the only combination that loads
 *     both SDKs without interop errors on Node 18-24.
 *
 * Usage:
 *   node x402/x402_helper.mjs encode-payment-required <json-stdin>
 *   node x402/x402_helper.mjs verify-payment-signature <json-stdin>
 *   node x402/x402_helper.mjs submit-vault-payment <json-stdin>
 *   node x402/x402_helper.mjs build-settle-response <json-stdin>
 *
 * Each command reads a JSON request from stdin and writes a JSON response to
 * stdout. Exit code 0 = success, 1 = failure.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// SDK imports — ESM namespace import is the ONLY path that works for both
// @make-software/casper-x402 (ESM build) and casper-js-sdk (CJS interop).
//
// `casper-js-sdk` v5 ships as CommonJS only. Node's CJS↔ESM interop wraps its
// `module.exports` as the `default` export of the ESM namespace object — the
// named exports (PrivateKey, KeyAlgorithm, etc.) are NOT exposed directly
// because the SDK is webpack-bundled (not statically analyzable). So we
// namespace-import and destructure from `.default`.
//
// `@make-software/casper-x402`'s CJS build (dist/cjs/index.js) has a bundler
// interop bug: `var { KeyAlgorithm } = import_default` is `undefined` when
// `require()`'d against casper-js-sdk. Its ESM build (dist/esm/index.mjs)
// uses a different interop path that works correctly. So we use the ESM
// named imports for casper-x402.
// ---------------------------------------------------------------------------
import * as casperSdk from 'casper-js-sdk';
const {
  PrivateKey,
  KeyAlgorithm,
  Args,
  CLValue,
  ContractCallBuilder,
  RpcClient,
} = casperSdk.default ?? casperSdk;

import {
  NETWORK_CASPER_TESTNET,
  SCHEME_EXACT,
  NetworkConfigs,
  chainNameFromNetwork,
  toFacilitatorCasperSigner,
} from '@make-software/casper-x402';
import { ExactCasperScheme as FacilitatorScheme } from '@make-software/casper-x402/exact/facilitator';
import {
  encodePaymentRequiredHeader,
  encodePaymentResponseHeader,
  decodePaymentSignatureHeader,
} from '@x402/core/http';

// ---------------------------------------------------------------------------
// Configuration (resolved from env or defaults — matches vaultwatch-x402.ts)
// ---------------------------------------------------------------------------

const CASPER_TESTNET = NETWORK_CASPER_TESTNET; // "casper:casper-test"
const CHAIN_NAME = chainNameFromNetwork(CASPER_TESTNET); // "casper-test"
const DEFAULT_RPC = NetworkConfigs[CASPER_TESTNET].rpcUrl; // https://node.testnet.casper.network/rpc
const X402_VERSION = 2;
const DEFAULT_MAX_TIMEOUT_SECONDS = 300;
const DEFAULT_PAYMENT_MOTES = 5_000_000_000; // 5 CSPR gas budget

const SUBSCRIBER_VAULT_CONTRACT_HASH =
  process.env.SUBSCRIBER_VAULT_HASH ||
  '0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c';
const SUBSCRIBER_VAULT_PACKAGE_HASH =
  process.env.SUBSCRIBER_VAULT_PACKAGE_HASH ||
  'd1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf';
const PAYEE_ACCOUNT_HASH =
  process.env.VAULTWATCH_PAYEE ||
  '000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68';

const DEFAULT_SECRET_KEY_PATH =
  process.env.VAULTWATCH_SIGNER_PEM || path.resolve(__dirname, '..', 'secret_key.pem');
const DEFAULT_KEY_ALGO = (process.env.VAULTWATCH_SIGNER_ALGO || 'secp256k1') === 'ed25519'
  ? KeyAlgorithm.ED25519
  : KeyAlgorithm.SECP256K1;

// ---------------------------------------------------------------------------
// JSON-RPC helper (same pattern as scripts/casper_deploy.cjs)
// ---------------------------------------------------------------------------

async function rpcPost(rpcUrl, authToken, method, params) {
  const body = JSON.stringify({ jsonrpc: '2.0', id: 1, method, params });
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = authToken;
  const r = await fetch(rpcUrl, { method: 'POST', headers, body });
  const data = await r.json();
  if (data.error) throw new Error(`RPC ${method}: ${JSON.stringify(data.error)}`);
  return data.result;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

// ---------------------------------------------------------------------------
// Command: encode-payment-required
// ---------------------------------------------------------------------------

async function cmdEncodePaymentRequired(req) {
  // req: { resourceUrl, description?, mimeType?, plan?, amountMotes? }
  const plan = req.plan || 'standard';
  const planPrices = {
    standard: 1_000_000_000,   // 1 CSPR
    premium: 5_000_000_000,    // 5 CSPR
  };
  const amount = req.amountMotes || String(planPrices[plan]);

  const paymentRequired = {
    x402Version: X402_VERSION,
    error: 'PAYMENT-SIGNATURE header is required',
    resource: {
      url: req.resourceUrl,
      description: req.description || `VaultWatch ${plan} intelligence query`,
      mimeType: req.mimeType || 'application/json',
      serviceName: 'VaultWatch',
      tags: ['defi', 'risk-intelligence', 'casper'],
    },
    accepts: [{
      scheme: SCHEME_EXACT,
      network: CASPER_TESTNET,
      asset: SUBSCRIBER_VAULT_PACKAGE_HASH,
      amount,
      payTo: PAYEE_ACCOUNT_HASH,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: {
        name: 'VaultWatch SubscriberVault',
        version: '1',
        description: 'Escrowed CSPR credit for VaultWatch intelligence queries',
      },
    }],
  };

  const header = encodePaymentRequiredHeader(paymentRequired);
  return {
    success: true,
    paymentRequired,
    paymentRequiredHeader: header,
  };
}

// ---------------------------------------------------------------------------
// Command: verify-payment-signature
// ---------------------------------------------------------------------------

async function cmdVerifyPaymentSignature(req) {
  // req: { paymentSignatureHeader } OR { paymentPayload, paymentRequirements }
  let payload, requirements;

  if (req.paymentSignatureHeader) {
    payload = decodePaymentSignatureHeader(req.paymentSignatureHeader);
    requirements = {
      scheme: SCHEME_EXACT,
      network: CASPER_TESTNET,
      asset: SUBSCRIBER_VAULT_PACKAGE_HASH,
      amount: (payload.accepted && payload.accepted.amount) || String(1_000_000_000),
      payTo: PAYEE_ACCOUNT_HASH,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: (payload.accepted && payload.accepted.extra) || { name: 'VaultWatch SubscriberVault', version: '1' },
    };
  } else {
    payload = req.paymentPayload;
    requirements = req.paymentRequirements;
  }

  // Load the facilitator signer from the deployer PEM (only for sig verify —
  // no on-chain submission happens in this command).
  const pemPath = req.signerPemPath || DEFAULT_SECRET_KEY_PATH;
  const pemContent = req.signerPem || fs.readFileSync(pemPath, 'utf8');
  const keyAlgo = (req.keyAlgorithm || 'secp256k1') === 'ed25519'
    ? KeyAlgorithm.ED25519
    : KeyAlgorithm.SECP256K1;
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const rpcUrl = req.rpcUrl || DEFAULT_RPC;
  const signer = await toFacilitatorCasperSigner(privateKey, rpcUrl);
  const scheme = new FacilitatorScheme(signer);

  const verifyResult = await scheme.verify(payload, requirements);
  return {
    success: true,
    isValid: verifyResult.isValid,
    payer: verifyResult.payer || null,
    invalidReason: verifyResult.invalidReason || null,
    invalidMessage: verifyResult.invalidMessage || null,
  };
}

// ---------------------------------------------------------------------------
// Command: submit-vault-payment
// ---------------------------------------------------------------------------

async function cmdSubmitVaultPayment(req) {
  // req: { subscriberAddress, amountMotes, lockBlocks?, autoRenew?,
  //        monthlySpendLimitMotes?, signerPemPath?, keyAlgorithm?,
  //        rpcUrl?, paymentMotes? }
  const subscriberAddress = req.subscriberAddress;
  const amountMotes = parseInt(req.amountMotes, 10);
  if (!subscriberAddress || !amountMotes) {
    throw new Error('subscriberAddress and amountMotes are required');
  }
  const lockBlocks = req.lockBlocks || 0;
  const autoRenew = req.autoRenew !== false;
  const monthlySpendLimit = req.monthlySpendLimitMotes || '0';
  const paymentMotes = req.paymentMotes || DEFAULT_PAYMENT_MOTES;
  const rpcUrl = req.rpcUrl || DEFAULT_RPC;
  const keyAlgo = (req.keyAlgorithm || 'secp256k1') === 'ed25519'
    ? KeyAlgorithm.ED25519
    : KeyAlgorithm.SECP256K1;

  const pemPath = req.signerPemPath || DEFAULT_SECRET_KEY_PATH;
  const pemContent = req.signerPem || fs.readFileSync(pemPath, 'utf8');

  if (process.env.DEBUG) {
    process.stderr.write(
      `[x402_helper] submit-vault-payment subscriber=${subscriberAddress} amount=${amountMotes} motes contract=${SUBSCRIBER_VAULT_CONTRACT_HASH}\n`
    );
  }

  // 1. Load the deployer's private key (the vault owner)
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const publicKey = privateKey.publicKey;

  // 2. Fetch current block height (required by open_vault's current_block arg).
  //    casper-js-sdk v5 split the old CasperServiceByJsonRPC into HttpHandler
  //    (transport) + RpcClient (client). The RpcClient constructor takes an
  //    HttpHandler instance, NOT a URL string. getLatestBlock() returns a
  //    BlockInfo object with a flat `.height` property (and `.block.height`).
  const handler = new casperSdk.default.HttpHandler(rpcUrl);
  const rpc = new RpcClient(handler);
  const latestBlock = await rpc.getLatestBlock();
  const currentBlock =
    latestBlock?.height ??
    latestBlock?.block?.height ??
    latestBlock?.rawJSON?.block_with_signatures?.block?.Version2?.header?.height ??
    0;
  if (process.env.DEBUG) {
    process.stderr.write(`[x402_helper] current block height = ${currentBlock}\n`);
  }

  // 3. Build runtime args for SubscriberVault.open_vault()
  //    (signature: open_vault(subscriber_address: String, initial_deposit: U512,
  //     lock_blocks: u64, auto_renew: bool, monthly_spend_limit: U512,
  //     current_block: u64) — see contracts/src/subscriber_vault.rs)
  //
  //    casper-js-sdk v5 has an inconsistent CLValue builder naming:
  //      • U512 → CLValue.newCLUInt512  (capital U)
  //      • u64  → CLValue.newCLUint64   (lowercase u — the only outlier)
  //    Both take a decimal string.
  const runtimeArgs = Args.fromMap({
    subscriber_address: CLValue.newCLString(subscriberAddress),
    initial_deposit: CLValue.newCLUInt512(String(amountMotes)),
    lock_blocks: CLValue.newCLUint64(String(lockBlocks)),
    auto_renew: CLValue.newCLValueBool(autoRenew),
    monthly_spend_limit: CLValue.newCLUInt512(monthlySpendLimit),
    current_block: CLValue.newCLUint64(String(currentBlock)),
  });

  // 4. Build the stored-contract-call deploy via casper-js-sdk v5
  //    ContractCallBuilder (same builder that produced 21 verified-success
  //    deploys — see proof/PROOF.md §8).
  const transaction = new ContractCallBuilder()
    .from(publicKey)
    .byHash(SUBSCRIBER_VAULT_CONTRACT_HASH)
    .entryPoint('open_vault')
    .runtimeArgs(runtimeArgs)
    .payment(paymentMotes)
    .chainName(CHAIN_NAME)
    .buildFor1_5();

  // 5. Sign
  transaction.sign(privateKey);
  const deployJson = transaction.toJSON();
  const deployHash = (deployJson && (deployJson.hash || (deployJson.deploy && deployJson.deploy.hash))) || '';
  if (!deployHash) {
    throw new Error('failed to compute deploy hash before submission');
  }
  if (process.env.DEBUG) {
    process.stderr.write(`[x402_helper] built+signed deploy ${deployHash}\n`);
  }

  // 6. Submit via account_put_deploy
  const submitResult = await rpcPost(rpcUrl, '', 'account_put_deploy', { deploy: deployJson });
  const submittedHash = submitResult.deploy_hash || submitResult.deployHash;
  if (!submittedHash) {
    throw new Error(`submit succeeded but no deploy_hash returned: ${JSON.stringify(submitResult)}`);
  }
  if (process.env.DEBUG) {
    process.stderr.write(`[x402_helper] submitted ${submittedHash}\n`);
  }

  // 7. Verify on-chain execution (poll info_get_deploy, ~3 min timeout)
  //    Casper 2.x: result.execution_info.execution_result.Version2
  //    { error_message: null } => SUCCESS
  const deadline = Date.now() + 180_000;
  let lastError = null;
  while (Date.now() < deadline) {
    await sleep(8_000);
    try {
      const result = await rpcPost(rpcUrl, '', 'info_get_deploy', { deploy_hash: submittedHash });
      const execInfo = result.execution_info;
      if (execInfo) {
        const blockHash = execInfo.block_hash || '';
        const execResult = execInfo.execution_result || {};
        const v2 = execResult.Version2;
        if (v2) {
          const success = v2.error_message === null || v2.error_message === undefined;
          // Build the SettleResponse + PAYMENT-RESPONSE header on success
          let settleResponseHeader = null;
          if (success) {
            const settleResponse = {
              success: true,
              payer: PAYEE_ACCOUNT_HASH,
              transaction: submittedHash,
              network: CASPER_TESTNET,
              amount: String(amountMotes),
              extensions: {
                casperDeployLink: `https://testnet.cspr.live/deploy/${submittedHash}`,
                contract: 'SubscriberVault',
                entryPoint: 'open_vault',
              },
            };
            settleResponseHeader = encodePaymentResponseHeader(settleResponse);
          }
          return {
            success,
            deployHash: submittedHash,
            blockHash,
            gasCostMotes: String(v2.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${submittedHash}`,
            settleResponseHeader,
            error: success ? null : v2.error_message,
          };
        }
        // Casper 1.x fallback
        if (execResult.Success) {
          const settleResponse = {
            success: true,
            payer: PAYEE_ACCOUNT_HASH,
            transaction: submittedHash,
            network: CASPER_TESTNET,
            amount: String(amountMotes),
            extensions: {
              casperDeployLink: `https://testnet.cspr.live/deploy/${submittedHash}`,
              contract: 'SubscriberVault',
              entryPoint: 'open_vault',
            },
          };
          return {
            success: true,
            deployHash: submittedHash,
            blockHash,
            gasCostMotes: String(execResult.Success.cost || '0'),
            link: `https://testnet.cspr.live/deploy/${submittedHash}`,
            settleResponseHeader: encodePaymentResponseHeader(settleResponse),
            error: null,
          };
        }
        if (execResult.Failure) {
          return {
            success: false,
            deployHash: submittedHash,
            blockHash,
            gasCostMotes: '0',
            link: `https://testnet.cspr.live/deploy/${submittedHash}`,
            settleResponseHeader: null,
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
    deployHash: submittedHash,
    blockHash: '',
    gasCostMotes: '0',
    link: `https://testnet.cspr.live/deploy/${submittedHash}`,
    settleResponseHeader: null,
    error: `verification timeout (last poll error: ${lastError || 'none'})`,
  };
}

// ---------------------------------------------------------------------------
// Command: build-settle-response (for when Python already has the deploy hash)
// ---------------------------------------------------------------------------

async function cmdBuildSettleResponse(req) {
  // req: { deployHash, payer, amountMotes, success, errorReason? }
  const settleResponse = {
    success: req.success,
    payer: req.payer || PAYEE_ACCOUNT_HASH,
    transaction: req.deployHash,
    network: CASPER_TESTNET,
    amount: String(req.amountMotes),
    ...(req.errorReason ? { errorReason: req.errorReason } : {}),
    extensions: {
      casperDeployLink: `https://testnet.cspr.live/deploy/${req.deployHash}`,
      contract: 'SubscriberVault',
      entryPoint: 'open_vault',
    },
  };
  return {
    success: true,
    settleResponse,
    settleResponseHeader: encodePaymentResponseHeader(settleResponse),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const command = process.argv[2];
  if (!command) {
    const valid = ['encode-payment-required', 'verify-payment-signature',
                   'submit-vault-payment', 'build-settle-response'];
    process.stderr.write(`Usage: node x402/x402_helper.mjs <command>\n`);
    process.stderr.write(`Commands: ${valid.join(', ')}\n`);
    process.stderr.write(`Each reads a JSON request from stdin.\n`);
    process.exit(2);
  }

  let req = {};
  try {
    const stdin = await readStdin();
    req = stdin.trim() ? JSON.parse(stdin) : {};
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: `invalid JSON stdin: ${e.message}` }));
    process.exit(1);
  }

  try {
    let result;
    switch (command) {
      case 'encode-payment-required':
        result = await cmdEncodePaymentRequired(req);
        break;
      case 'verify-payment-signature':
        result = await cmdVerifyPaymentSignature(req);
        break;
      case 'submit-vault-payment':
        result = await cmdSubmitVaultPayment(req);
        break;
      case 'build-settle-response':
        result = await cmdBuildSettleResponse(req);
        break;
      default:
        console.log(JSON.stringify({ success: false, error: `unknown command: ${command}` }));
        process.exit(1);
    }
    console.log(JSON.stringify(result));
    process.exit(result.success === false ? 1 : 0);
  } catch (e) {
    console.log(JSON.stringify({ success: false, error: e.message }));
    process.exit(1);
  }
}

main();
