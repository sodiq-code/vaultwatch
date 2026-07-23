#!/usr/bin/env node
/**
 * VaultWatch — WCSPR x402 Helper CLI (ESM)
 *
 * This is the WCSPR-specific bridge between the Python FastAPI server
 * (api/main.py) and the official @make-software/casper-x402 /
 * @x402/core JavaScript SDKs. It handles the three operations that
 * require the JS SDK for WCSPR (CEP-18) payment processing:
 *
 *   1. create-wcspr-payment-required — build the x402 v2 PaymentRequired
 *                                      JSON + base64 PAYMENT-REQUIRED header
 *                                      with WCSPR CEP-18 as the asset
 *   2. check-facilitator-supported   — check whether the CSPR.cloud
 *                                      facilitator supports WCSPR x402 payments
 *   3. verify-wcspr-payment          — decode + cryptographically verify a
 *                                      client's PAYMENT-SIGNATURE header for
 *                                      WCSPR (CEP-18 transfer_with_auth)
 *
 * This follows the same stdin/stdout JSON pattern as x402_helper.mjs.
 * Each command reads a JSON request from stdin and writes a JSON response
 * to stdout. Exit code 0 = success, 1 = failure.
 *
 * Why ESM (.mjs)?
 *   - Same reason as x402_helper.mjs: casper-js-sdk v5 ships as CommonJS
 *     only, and @make-software/casper-x402's ESM build is the only path
 *     that works correctly with the CJS↔ESM interop.
 *   - `import * as casperSdk from 'casper-js-sdk'` (namespace import)
 *     is the ONLY combination that loads both SDKs without interop errors
 *     on Node 18-24.
 *
 * Usage:
 *   node x402/wcspr_helper.mjs create-wcspr-payment-required <json-stdin>
 *   node x402/wcspr_helper.mjs check-facilitator-supported <json-stdin>
 *   node x402/wcspr_helper.mjs verify-wcspr-payment <json-stdin>
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
// See x402_helper.mjs for the detailed explanation of why this interop
// pattern is required.
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
// Configuration (resolved from env or defaults — matches wcspr-x402-path.ts)
// ---------------------------------------------------------------------------

const CASPER_TESTNET = NETWORK_CASPER_TESTNET; // "casper:casper-test"
const CHAIN_NAME = chainNameFromNetwork(CASPER_TESTNET); // "casper-test"
const DEFAULT_RPC = NetworkConfigs[CASPER_TESTNET].rpcUrl; // https://node.testnet.casper.network/rpc
const X402_VERSION = 2;
const DEFAULT_MAX_TIMEOUT_SECONDS = 300;
const WCSPR_DECIMALS = 9;
const CEP18_TRANSFER_WITH_AUTH = 'transfer_with_authorization';

const CSPR_TO_MOTES = 1_000_000_000;
const PLAN_PRICES = {
  standard: 1 * CSPR_TO_MOTES, // 1 WCSPR (= 1 CSPR)
  premium: 5 * CSPR_TO_MOTES,  // 5 WCSPR (= 5 CSPR)
};

// WCSPR CEP-18 contract config (PLACEHOLDER hashes — to be replaced)
const WCSPR_CONTRACT_HASH =
  process.env.WCSPR_CONTRACT_HASH || 'wcspr-contract-hash-placeholder'; // PLACEHOLDER
const WCSPR_PACKAGE_HASH =
  process.env.WCSPR_PACKAGE_HASH || 'wcspr-package-hash-placeholder'; // PLACEHOLDER
const WCSPR_SWAP_URL = 'https://testnet.cspr.trade';

// SubscriberVault (native CSPR path — used in dual-path verification)
const SUBSCRIBER_VAULT_PACKAGE_HASH =
  process.env.SUBSCRIBER_VAULT_PACKAGE_HASH ||
  '68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211';

const PAYEE_ACCOUNT_HASH =
  process.env.VAULTWATCH_PAYEE ||
  '000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68';

const CSPR_CLOUD_API_URL =
  process.env.CSPR_CLOUD_API_URL || 'https://api.cspr.cloud';
const CSPR_CLOUD_API_KEY =
  process.env.CSPR_CLOUD_API_KEY || '';

const DEFAULT_SECRET_KEY_PATH =
  process.env.VAULTWATCH_SIGNER_PEM || path.resolve(__dirname, '..', 'secret_key.pem');
const DEFAULT_KEY_ALGO = (process.env.VAULTWATCH_SIGNER_ALGO || 'secp256k1') === 'ed25519'
  ? KeyAlgorithm.ED25519
  : KeyAlgorithm.SECP256K1;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

/**
 * Make a fetch request to the CSPR.cloud facilitator API with Bearer auth.
 */
async function facilitatorFetch(endpoint, method, body = null) {
  const url = `${CSPR_CLOUD_API_URL}${endpoint}`;
  const headers = {
    'Authorization': `Bearer ${CSPR_CLOUD_API_KEY}`,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const response = await fetch(url, opts);
  const text = await response.text();

  if (!response.ok) {
    throw new Error(`CSPR.cloud ${endpoint} returned ${response.status}: ${text}`);
  }

  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

// ---------------------------------------------------------------------------
// Command: create-wcspr-payment-required
// ---------------------------------------------------------------------------

async function cmdCreateWCSPRPaymentRequired(req) {
  // req: { resourceUrl, description?, mimeType?, plan?, amountMotes? }
  const plan = req.plan || 'standard';
  const amount = req.amountMotes || String(PLAN_PRICES[plan]);

  const paymentRequired = {
    x402Version: X402_VERSION,
    error: 'PAYMENT-SIGNATURE header is required (WCSPR CEP-18 transfer_with_authorization)',
    resource: {
      url: req.resourceUrl,
      description: req.description || `VaultWatch ${plan} intelligence query (WCSPR payment)`,
      mimeType: req.mimeType || 'application/json',
      serviceName: 'VaultWatch',
      tags: ['defi', 'risk-intelligence', 'casper', 'wcspr', 'cep-18'],
    },
    accepts: [{
      scheme: SCHEME_EXACT,
      network: CASPER_TESTNET,
      asset: WCSPR_PACKAGE_HASH, // WCSPR CEP-18 package hash (PLACEHOLDER)
      amount,
      payTo: PAYEE_ACCOUNT_HASH,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: {
        name: 'Wrapped CSPR',
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization payment for VaultWatch intelligence queries',
        symbol: 'WCSPR',
        decimals: WCSPR_DECIMALS,
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_SWAP_URL,
      },
    }],
  };

  const header = encodePaymentRequiredHeader(paymentRequired);
  return {
    success: true,
    paymentRequired,
    paymentRequiredHeader: header,
    wcsprConfig: {
      contractHash: WCSPR_CONTRACT_HASH,
      packageHash: WCSPR_PACKAGE_HASH,
      name: 'Wrapped CSPR',
      symbol: 'WCSPR',
      decimals: WCSPR_DECIMALS,
      entryPoints: ['transfer', 'transfer_from', CEP18_TRANSFER_WITH_AUTH],
      swapUrl: WCSPR_SWAP_URL,
    },
  };
}

// ---------------------------------------------------------------------------
// Command: check-facilitator-supported
// ---------------------------------------------------------------------------

async function cmdCheckFacilitatorSupported(req) {
  // req: { network?, asset?, scheme? } (all optional)
  const network = req.network || CASPER_TESTNET;
  const asset = req.asset || WCSPR_PACKAGE_HASH;
  const scheme = req.scheme || SCHEME_EXACT;

  try {
    const queryParams = new URLSearchParams();
    queryParams.set('network', network);
    queryParams.set('asset', asset);
    queryParams.set('scheme', scheme);
    const endpoint = `/supported?${queryParams.toString()}`;

    const data = await facilitatorFetch(endpoint, 'GET');
    return {
      success: true,
      supported: data.supported ?? true,
      schemes: data.schemes ?? [],
      networks: data.networks ?? [],
      assets: data.assets ?? [],
    };
  } catch (e) {
    return {
      success: false,
      supported: false,
      error: e.message,
    };
  }
}

// ---------------------------------------------------------------------------
// Command: verify-wcspr-payment
// ---------------------------------------------------------------------------

async function cmdVerifyWCSPRPayment(req) {
  // req: { paymentSignatureHeader } OR { paymentPayload, paymentRequirements }
  //      useFacilitator? (boolean — also verify via CSPR.cloud)
  let payload, requirements;
  const useFacilitator = req.useFacilitator === true;

  if (req.paymentSignatureHeader) {
    payload = decodePaymentSignatureHeader(req.paymentSignatureHeader);
    requirements = {
      scheme: SCHEME_EXACT,
      network: CASPER_TESTNET,
      asset: WCSPR_PACKAGE_HASH, // WCSPR CEP-18 package hash
      amount: (payload.accepted && payload.accepted.amount) || String(PLAN_PRICES.standard),
      payTo: PAYEE_ACCOUNT_HASH,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: (payload.accepted && payload.accepted.extra) || {
        name: 'Wrapped CSPR',
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization payment',
        symbol: 'WCSPR',
        decimals: WCSPR_DECIMALS,
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_SWAP_URL,
      },
    };
  } else {
    payload = req.paymentPayload;
    requirements = req.paymentRequirements;
  }

  // Load the facilitator signer from the deployer PEM
  const pemPath = req.signerPemPath || DEFAULT_SECRET_KEY_PATH;
  const pemContent = req.signerPem || fs.readFileSync(pemPath, 'utf8');
  const keyAlgo = (req.keyAlgorithm || 'secp256k1') === 'ed25519'
    ? KeyAlgorithm.ED25519
    : KeyAlgorithm.SECP256K1;
  const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
  const rpcUrl = req.rpcUrl || DEFAULT_RPC;
  const signer = await toFacilitatorCasperSigner(privateKey, rpcUrl);
  const scheme = new FacilitatorScheme(signer);

  // Local verification (ExactCasperScheme)
  const verifyResult = await scheme.verify(payload, requirements);

  const result = {
    success: true,
    isValid: verifyResult.isValid,
    payer: verifyResult.payer || null,
    invalidReason: verifyResult.invalidReason || null,
    invalidMessage: verifyResult.invalidMessage || null,
    verificationPath: 'local',
    asset: WCSPR_PACKAGE_HASH,
  };

  // Optional: also verify via CSPR.cloud facilitator
  if (useFacilitator && CSPR_CLOUD_API_KEY) {
    try {
      const facilitatorResult = await facilitatorFetch('/verify', 'POST', {
        payload,
        requirements,
      });

      // If facilitator found issues that local verification missed
      if (!facilitatorResult.isValid && result.isValid) {
        result.isValid = false;
        result.invalidReason = facilitatorResult.invalidReason || 'facilitator verification failed';
        result.invalidMessage = facilitatorResult.invalidMessage || facilitatorResult.error || '';
      }

      // Prefer facilitator payer result (it has on-chain state access)
      if (facilitatorResult.isValid && facilitatorResult.payer) {
        result.payer = facilitatorResult.payer;
      }

      result.facilitatorResult = {
        isValid: facilitatorResult.isValid ?? false,
        payer: facilitatorResult.payer ?? null,
        invalidReason: facilitatorResult.invalidReason ?? null,
        invalidMessage: facilitatorResult.invalidMessage ?? null,
      };
      result.verificationPath = 'dual';
    } catch (e) {
      result.facilitatorError = e.message;
      // Don't downgrade local result if facilitator is unavailable
      result.verificationPath = 'local-only';
    }
  }

  // Also attempt native CSPR (SubscriberVault) verification for dual-path info
  if (req.checkDualPath === true) {
    const nativeRequirements = {
      scheme: SCHEME_EXACT,
      network: CASPER_TESTNET,
      asset: SUBSCRIBER_VAULT_PACKAGE_HASH,
      amount: (payload.accepted && payload.accepted.amount) || String(PLAN_PRICES.standard),
      payTo: PAYEE_ACCOUNT_HASH,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: (payload.accepted && payload.accepted.extra) || {
        name: 'VaultWatch SubscriberVault',
        version: '1',
        description: 'Escrowed CSPR credit for VaultWatch intelligence queries',
      },
    };

    try {
      const nativeResult = await scheme.verify(payload, nativeRequirements);
      result.nativePath = {
        isValid: nativeResult.isValid,
        payer: nativeResult.payer || null,
        invalidReason: nativeResult.invalidReason || null,
        asset: SUBSCRIBER_VAULT_PACKAGE_HASH,
      };
    } catch (e) {
      result.nativePath = {
        isValid: false,
        invalidReason: e.message,
        asset: SUBSCRIBER_VAULT_PACKAGE_HASH,
      };
    }

    // Determine which path to use
    if (result.isValid && result.nativePath?.isValid) {
      // Both paths verified — choose based on client's intended asset
      const clientAsset = (payload.accepted && payload.accepted.asset) || '';
      result.recommendedPath = clientAsset === WCSPR_PACKAGE_HASH ? 'wcspr' : 'native';
    } else if (result.isValid) {
      result.recommendedPath = 'wcspr';
    } else if (result.nativePath?.isValid) {
      result.recommendedPath = 'native';
    } else {
      result.recommendedPath = 'none';
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const command = process.argv[2];
  if (!command) {
    const valid = ['create-wcspr-payment-required', 'check-facilitator-supported',
                   'verify-wcspr-payment'];
    process.stderr.write(`Usage: node x402/wcspr_helper.mjs <command>\n`);
    process.stderr.write(`Commands: ${valid.join(', ')}\n`);
    process.stderr.write(`Each reads a JSON request from stdin.\n`);
    process.stderr.write(`\nEnvironment variables:\n`);
    process.stderr.write(`  WCSPR_CONTRACT_HASH  — WCSPR CEP-18 contract hash (PLACEHOLDER)\n`);
    process.stderr.write(`  WCSPR_PACKAGE_HASH   — WCSPR CEP-18 package hash (PLACEHOLDER)\n`);
    process.stderr.write(`  CSPR_CLOUD_API_KEY   — CSPR.cloud facilitator API key\n`);
    process.stderr.write(`  CSPR_CLOUD_API_URL   — CSPR.cloud base URL (default: https://api.cspr.cloud)\n`);
    process.stderr.write(`  VAULTWATCH_PAYEE     — Payee account hash\n`);
    process.stderr.write(`  VAULTWATCH_SIGNER_PEM — Path to signer PEM file\n`);
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
      case 'create-wcspr-payment-required':
        result = await cmdCreateWCSPRPaymentRequired(req);
        break;
      case 'check-facilitator-supported':
        result = await cmdCheckFacilitatorSupported(req);
        break;
      case 'verify-wcspr-payment':
        result = await cmdVerifyWCSPRPayment(req);
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
