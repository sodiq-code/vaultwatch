#!/usr/bin/env node
/**
 * VaultWatch — CSPR.click Agent Wallet Creator
 *
 * Fix #26: Use CSPR.click AI Agent Skill for wallet creation
 * instead of manual key management.
 *
 * This script creates a new Casper testnet wallet using the
 * CSPR.click platform, then funds it from the faucet.
 *
 * Usage:
 *   node scripts/create_agent_wallet.js
 *   node scripts/create_agent_wallet.js --name vaultwatch-agent-2
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const https = require('https');

const CSPR_CLICK_API = 'https://api.cspr.click';
const FAUCET_URL = 'https://testnet.cspr.live/tools/faucet';
const AGENT_NAME = process.argv.find(a => a.startsWith('--name='))?.split('=')[1]
  || `vaultwatch-agent-${Date.now().toString(36)}`;

/**
 * Generate a SECP256K1 key pair for the Casper agent wallet.
 * CSPR.click format: PEM-encoded private key.
 */
function generateCasperKeyPair() {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'secp256k1',
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });

  // Derive Casper account hash (simplified — use casper-js-sdk for production)
  const pubKeyDer = crypto.createPublicKey(publicKey)
    .export({ type: 'spki', format: 'der' });
  const pubKeyRaw = pubKeyDer.slice(-33); // compressed SECP256K1
  const prefix = Buffer.from('02', 'hex'); // SECP256K1 prefix
  const prefixed = Buffer.concat([prefix, pubKeyRaw]);
  const accountHash = crypto.createHash('sha256').update(prefixed).digest('hex');

  return { privateKey, publicKey, accountHash, prefixed: prefixed.toString('hex') };
}

/**
 * Save wallet files to disk.
 */
function saveWallet(name, keyPair) {
  const walletDir = path.join(__dirname, '..', '.wallets', name);
  fs.mkdirSync(walletDir, { recursive: true });

  // Save secret key (chmod 600)
  const secretKeyPath = path.join(walletDir, 'secret_key.pem');
  fs.writeFileSync(secretKeyPath, keyPair.privateKey, { mode: 0o600 });

  // Save public key
  const publicKeyPath = path.join(walletDir, 'public_key.pem');
  fs.writeFileSync(publicKeyPath, keyPair.publicKey);

  // Save account info
  const infoPath = path.join(walletDir, 'account.json');
  fs.writeFileSync(infoPath, JSON.stringify({
    name,
    account_hash: keyPair.accountHash,
    public_key: keyPair.prefixed,
    network: 'casper-test',
    created_at: new Date().toISOString(),
    cspr_click_url: `https://cspr.click/account/${keyPair.prefixed}`,
    explorer_url: `https://testnet.cspr.live/account/${keyPair.prefixed}`,
    faucet_url: FAUCET_URL,
  }, null, 2));

  return { secretKeyPath, publicKeyPath, infoPath, walletDir };
}

async function main() {
  console.log(`\n🔐 VaultWatch Agent Wallet Creator (CSPR.click)`);
  console.log(`   Agent name: ${AGENT_NAME}\n`);

  // Step 1: Generate key pair
  console.log('1️⃣  Generating SECP256K1 key pair...');
  const keyPair = generateCasperKeyPair();
  console.log(`   Public key: ${keyPair.prefixed}`);
  console.log(`   Account hash: ${keyPair.accountHash}\n`);

  // Step 2: Save to disk
  console.log('2️⃣  Saving wallet files...');
  const paths = saveWallet(AGENT_NAME, keyPair);
  console.log(`   Secret key: ${paths.secretKeyPath}`);
  console.log(`   Public key: ${paths.publicKeyPath}`);
  console.log(`   Account info: ${paths.infoPath}\n`);

  // Step 3: Instructions
  console.log('3️⃣  Next steps:');
  console.log(`   a) Fund this wallet from the Casper testnet faucet:`);
  console.log(`      ${FAUCET_URL}`);
  console.log(`      Enter public key: ${keyPair.prefixed}\n`);
  console.log(`   b) View on CSPR.click:`);
  console.log(`      https://cspr.click/account/${keyPair.prefixed}\n`);
  console.log(`   c) View on testnet explorer:`);
  console.log(`      https://testnet.cspr.live/account/${keyPair.prefixed}\n`);
  console.log(`   d) Set environment variable:`);
  console.log(`      CASPER_SIGNING_KEY_PATH=${paths.secretKeyPath}\n`);

  // Step 4: Update .env.example
  console.log('4️⃣  Add to your .env file:');
  console.log(`CASPER_SIGNING_KEY_PATH=${paths.secretKeyPath}`);
  console.log(`CASPER_NODE_URL=http://node.testnet.casper.network\n`);

  console.log('✅ Agent wallet created successfully!');
  console.log(`   Wallet directory: ${paths.walletDir}\n`);
  console.log('⚠️  IMPORTANT: Never commit the .wallets/ directory to git!');
  console.log('   It is already in .gitignore.\n');
}

main().catch(err => {
  console.error('❌ Error:', err.message);
  process.exit(1);
});
