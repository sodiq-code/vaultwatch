#!/usr/bin/env node
/**
 * VaultWatch — x402 End-to-End Live Verification Script
 *
 * Exercises the REAL x402 v2 payment flow end-to-end on Casper testnet:
 *
 *   1. Build a real x402 v2 PaymentRequired object + base64 PAYMENT-REQUIRED
 *      header via the OFFICIAL @make-software/casper-x402 SDK +
 *      @x402/core/http encoder.
 *   2. Build, sign, submit, and on-chain verify a REAL
 *      `SubscriberVault.open_vault()` stored-contract deploy on Casper
 *      testnet via casper-js-sdk v5's ContractCallBuilder.
 *   3. Build the x402 v2 SettleResponse carrying the verified deploy hash,
 *      encoded as the base64 PAYMENT-RESPONSE header.
 *   4. Write the full proof (deploy hash, block hash, gas cost, PAYMENT-
 *      REQUIRED header, PAYMENT-RESPONSE header, SettleResponse JSON) to
 *      proof/x402_payment_hashes.json — which is the "verified payment hash"
 *      artifact referenced from proof/PROOF.md §11.
 *
 * Run:
 *   node scripts/demo_x402_payment.mjs
 *
 * No arguments — the subscriber address, plan, and amount are baked in.
 * The deployer is the funded Account 2 (secret_key.pem at repo root).
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

// Reuse the same helper for the heavy lifting.
const HELPER = path.join(REPO_ROOT, 'x402', 'x402_helper.mjs');

async function runHelper(command, payload) {
  const proc = await spawnNode([HELPER, command], payload);
  if (proc.exitCode !== 0) {
    throw new Error(`helper ${command} exited ${proc.exitCode}: ${proc.stderr}`);
  }
  const result = JSON.parse(proc.stdout);
  if (!result.success) {
    throw new Error(`helper ${command} failed: ${result.error}`);
  }
  return result;
}

function spawnNode(args, stdinPayload) {
  const { spawn } = require('child_process');
  return new Promise((resolve) => {
    const child = spawn('node', args, { cwd: REPO_ROOT });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('close', (code) => resolve({ exitCode: code, stdout, stderr }));
    child.stdin.write(JSON.stringify(stdinPayload));
    child.stdin.end();
  });
}

// Node 24+: import 'child_process' synchronously via createRequire.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

async function main() {
  console.log('=== VaultWatch — x402 v2 End-to-End Live Verification ===\n');

  // ---- Configuration ----------------------------------------------------
  const SUBSCRIBER_ADDRESS = 'subscriber-vaultwatch-demo-001';
  const PLAN = 'standard';                 // 1 CSPR per query
  const PAYMENT_AMOUNT_MOTES = 1_000_000_000; // 1 CSPR (matches standard plan)
  const PEM_PATH = path.join(REPO_ROOT, 'secret_key.pem');

  if (!fs.existsSync(PEM_PATH)) {
    console.error(`✗ Deployer PEM not found at ${PEM_PATH}`);
    process.exit(1);
  }

  console.log(`Subscriber:    ${SUBSCRIBER_ADDRESS}`);
  console.log(`Plan:          ${PLAN} (1 CSPR = 1e9 motes)`);
  console.log(`Amount:        ${PAYMENT_AMOUNT_MOTES} motes (${PAYMENT_AMOUNT_MOTES / 1e9} CSPR)`);
  console.log(`Deployer PEM:  ${PEM_PATH}`);
  console.log('');

  // ---- Step 1: Build the x402 v2 PaymentRequired ------------------------
  console.log('[1/4] Building x402 v2 PaymentRequired via @make-software/casper-x402 + @x402/core...');
  const enc = await runHelper('encode-payment-required', {
    resourceUrl: `https://api.vaultwatch.io/intel/${SUBSCRIBER_ADDRESS}`,
    description: `VaultWatch ${PLAN} subscription — ${PAYMENT_AMOUNT_MOTES / 1e9} CSPR escrowed`,
    plan: PLAN,
    amountMotes: String(PAYMENT_AMOUNT_MOTES),
  });
  const paymentRequired = enc.paymentRequired;
  const paymentRequiredHeader = enc.paymentRequiredHeader;
  console.log('  ✅ PaymentRequired built.');
  console.log('     x402Version =', paymentRequired.x402Version);
  console.log('     scheme      =', paymentRequired.accepts[0].scheme);
  console.log('     network     =', paymentRequired.accepts[0].network);
  console.log('     asset       =', paymentRequired.accepts[0].asset);
  console.log('     payTo       =', paymentRequired.accepts[0].payTo);
  console.log('     amount      =', paymentRequired.accepts[0].amount, 'motes');
  console.log('     PAYMENT-REQUIRED header length =', paymentRequiredHeader.length, 'chars');
  console.log('');

  // ---- Step 2: Submit the REAL on-chain payment deploy ------------------
  console.log('[2/4] Submitting REAL SubscriberVault.open_vault() deploy via casper-js-sdk v5...');
  console.log('     (this signs with the deployer key + submits to https://node.testnet.casper.network/rpc)');
  console.log('     (verification polls info_get_deploy until Version2 execution_result is available)');
  const submit = await runHelper('submit-vault-payment', {
    subscriberAddress: SUBSCRIBER_ADDRESS,
    amountMotes: PAYMENT_AMOUNT_MOTES,
    lockBlocks: 0,
    autoRenew: true,
    monthlySpendLimitMotes: '0',
    signerPemPath: PEM_PATH,
    keyAlgorithm: 'secp256k1',
  });
  if (!submit.success) {
    console.error('  ✗ On-chain deploy FAILED:', submit.error);
    console.error('     link:', submit.link);
    process.exit(1);
  }
  console.log('  ✅ On-chain deploy VERIFIED SUCCESS.');
  console.log('     deployHash =', submit.deployHash);
  console.log('     blockHash  =', submit.blockHash);
  console.log('     gas cost   =', submit.gasCostMotes, 'motes (',
    (parseInt(submit.gasCostMotes, 10) / 1e9).toFixed(4), 'CSPR)');
  console.log('     link       =', submit.link);
  console.log('');

  // ---- Step 3: Build the SettleResponse + PAYMENT-RESPONSE header -------
  console.log('[3/4] Building x402 v2 SettleResponse + PAYMENT-RESPONSE header...');
  const settle = await runHelper('build-settle-response', {
    deployHash: submit.deployHash,
    payer: '000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68',
    amountMotes: String(PAYMENT_AMOUNT_MOTES),
    success: true,
  });
  console.log('  ✅ SettleResponse built.');
  console.log('     transaction =', settle.settleResponse.transaction);
  console.log('     network     =', settle.settleResponse.network);
  console.log('     success     =', settle.settleResponse.success);
  console.log('     PAYMENT-RESPONSE header length =', settle.settleResponseHeader.length, 'chars');
  console.log('');

  // ---- Step 4: Write the proof artifact ---------------------------------
  console.log('[4/4] Writing proof artifact to proof/x402_payment_hashes.json...');
  const proof = {
    x402_version: 2,
    scheme: 'exact',
    network: 'casper:casper-test',
    chain_name: 'casper-test',
    sdk: {
      '@make-software/casper-x402': '1.0.0',
      '@x402/core': '2.15.0',
      'casper-js-sdk': '5.0.12',
    },
    flow: 'SubscriberVault.open_vault() stored-contract deploy on Casper testnet',
    subscriber_address: SUBSCRIBER_ADDRESS,
    plan: PLAN,
    amount_motes: String(PAYMENT_AMOUNT_MOTES),
    amount_cspr: PAYMENT_AMOUNT_MOTES / 1e9,
    payment_required: paymentRequired,
    payment_required_header: paymentRequiredHeader,
    on_chain_deploy: {
      deploy_hash: submit.deployHash,
      block_hash: submit.blockHash,
      gas_cost_motes: submit.gasCostMotes,
      gas_cost_cspr: parseInt(submit.gasCostMotes, 10) / 1e9,
      link: submit.link,
      contract_entry_point: 'open_vault',
      contract_hash: paymentRequired.accepts[0].asset,
      contract_package_hash: paymentRequired.accepts[0].asset,
    },
    settle_response: settle.settleResponse,
    payment_response_header: settle.settleResponseHeader,
    payee_account_hash: paymentRequired.accepts[0].payTo,
    verified_at_utc: new Date().toISOString(),
  };
  const proofPath = path.join(REPO_ROOT, 'proof', 'x402_payment_hashes.json');
  fs.writeFileSync(proofPath, JSON.stringify(proof, null, 2) + '\n', 'utf8');
  console.log('  ✅ Proof written to', path.relative(REPO_ROOT, proofPath));
  console.log('');

  // ---- Summary ----------------------------------------------------------
  console.log('=== x402 v2 End-to-End Live Verification: PASSED ===');
  console.log('');
  console.log('Verified payment hash (the artifact for proof/PROOF.md §11):');
  console.log('  deploy_hash =', submit.deployHash);
  console.log('  block_hash  =', submit.blockHash);
  console.log('  link        =', submit.link);
  console.log('');
  console.log('All four x402 components are REAL and verified:');
  console.log('  1. @make-software/casper-x402 + @x402/core build a real PaymentRequired.');
  console.log('  2. casper-js-sdk v5 signs + submits a real open_vault() deploy.');
  console.log('  3. The deploy is verified-success on Casper testnet (Version2.error_message == null).');
  console.log('  4. The SettleResponse carries the verified deploy hash as the PAYMENT-RESPONSE.');
}

main().catch((e) => {
  console.error('FATAL:', e.message);
  console.error(e.stack);
  process.exit(1);
});
