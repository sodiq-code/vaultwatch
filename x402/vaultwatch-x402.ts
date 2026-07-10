/**
 * VaultWatch — Official x402 Payment Helper
 *
 * This module integrates the OFFICIAL @make-software/casper-x402 SDK,
 * replacing the previous home-rolled x402 simulation in agents/intel_agent.py.
 *
 * The official SDK provides:
 *   - Standardized HTTP 402 Payment Required response format
 *   - On-chain payment verification on Casper
 *   - Facilitator-compatible payment protocol
 *   - SubscriberVault + SentinelCredit contract bindings
 *
 * Installation:
 *   npm install @make-software/casper-x402
 *   # or pnpm add @make-software/casper-x402
 *
 * Usage:
 *   import { VaultWatchX402 } from './x402/vaultwatch-x402.js';
 *   const x402 = new VaultWatchX402({ network: 'testnet' });
 *   const result = await x402.subscribe({
 *     subscriberAddress,
 *     plan: 'premium',
 *     paymentAmountCSPR: 10,
 *   });
 *
 * Architecture:
 *   Client → HTTP request to VaultWatch API
 *   VaultWatch → returns 402 with x402 payment parameters
 *   Client → signs payment to SubscriberVault contract via x402 SDK
 *   SDK → verifies payment on-chain
 *   VaultWatch → serves the intelligence finding
 *   SubscriberVault.deduct() → records the spend on-chain
 */

import { CasperClient, CasperServiceByJsonRPC, Keys } from 'casper-js-sdk';

// Type-only import to avoid hard dependency at parse time. The actual
// @make-software/casper-x402 package must be installed by the user.
// If it's not installed, the class methods will throw a clear error.
export interface CasperX402Client {
  createPaymentRequest(params: PaymentRequestParams): PaymentRequest;
  verifyPayment(paymentProof: PaymentProof): Promise<PaymentVerification>;
  facilitatorUrl: string;
}

export interface PaymentRequestParams {
  payTo: string;           // SubscriberVault contract hash
  payAmount: string;       // in motes (1 CSPR = 1e9 motes)
  network: string;         // 'casper-test'
  paymentType: 'escrow' | 'direct';
  expiresAt: number;       // unix timestamp
  memo?: string;
}

export interface PaymentRequest {
  version: number;
  maxTotalAmount: string;
  paymentRequirements: Array<{
    scheme: 'casper-x402';
    network: string;
    assetScale: number;
    payTo: string;
    maxAmountRequired: string;
    resource: string;
    description?: string;
    mimeTypes?: string[];
  }>;
  intermediates?: string[];
}

export interface PaymentProof {
  paymentHash: string;
  signature: string;
  payerPubKey: string;
  amountPaid: string;
  blockHash?: string;
}

export interface PaymentVerification {
  verified: boolean;
  error?: string;
  paymentHash?: string;
  blockHash?: string;
}

export interface SubscribeParams {
  subscriberAddress: string;
  plan: 'standard' | 'premium';
  paymentAmountCSPR: number;
  lockBlocks?: number;
  signerSecretKey?: string;  // PEM string; if omitted, returns unsigned tx for user to sign
}

export interface SubscribeResult {
  success: boolean;
  deployHash?: string;
  contractPackageHash?: string;
  escrowBalanceMotes: string;
  queryPriceMotes: string;
  expectedQueries: number;
  paymentRequest?: PaymentRequest;
  error?: string;
}

const NETWORK_URLS = {
  testnet: 'https://rpc.testnet.casper.network/rpc',
  mainnet: 'https://rpc.casper.network/rpc',
} as const;

const CSPR_TO_MOTES = 1_000_000_000;
const PLAN_PRICES = {
  standard: 1 * CSPR_TO_MOTES,   // 1 CSPR per query
  premium: 5 * CSPR_TO_MOTES,    // 5 CSPR per query (includes RWA)
} as const;

export class VaultWatchX402 {
  private network: 'testnet' | 'mainnet';
  private nodeUrl: string;
  private x402Client: CasperX402Client | null = null;

  constructor(opts: { network?: 'testnet' | 'mainnet'; nodeUrl?: string } = {}) {
    this.network = opts.network ?? 'testnet';
    this.nodeUrl = opts.nodeUrl ?? NETWORK_URLS[this.network];
  }

  /**
   * Lazily load the official @make-software/casper-x402 SDK.
   * Throws a clear error if not installed.
   */
  private async loadX402SDK(): Promise<CasperX402Client> {
    if (this.x402Client) return this.x402Client;
    try {
      // Dynamic import so this module loads even if the SDK isn't installed yet
      const mod = await import('@make-software/casper-x402');
      const facilitatorUrl = this.network === 'testnet'
        ? 'https://x402.testnet.casper.network'
        : 'https://x402.casper.network';
      this.x402Client = new mod.CasperX402Client({ facilitatorUrl, network: this.network });
      return this.x402Client;
    } catch (e) {
      throw new Error(
        '@make-software/casper-x402 is not installed. Run: npm install @make-software/casper-x402'
      );
    }
  }

  /**
   * Subscribe to VaultWatch intelligence via official x402 protocol.
   * Escrows payment in SubscriberVault contract.
   */
  async subscribe(params: SubscribeParams): Promise<SubscribeResult> {
    const motes = Math.floor(params.paymentAmountCSPR * CSPR_TO_MOTES);
    const queryPrice = PLAN_PRICES[params.plan];

    try {
      const sdk = await this.loadX402SDK();

      // 1. Create the x402 payment request
      const paymentRequest = sdk.createPaymentRequest({
        payTo: process.env.SUBSCRIBER_VAULT_HASH ?? '<deploy-and-set-env>',
        payAmount: motes.toString(),
        network: this.network === 'testnet' ? 'casper-test' : 'casper',
        paymentType: 'escrow',
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
        memo: `VaultWatch ${params.plan} subscription`,
      });

      // 2. If a signer key is provided, sign + submit the payment deploy
      let deployHash: string | undefined;
      if (params.signerSecretKey) {
        const keyPair = Keys.Secp256K1.parsePrivateKey(
          Buffer.from(params.signerSecretKey, 'hex')
        );
        // Build the SubscriberVault.open_vault() deploy
        // (in production, use the casper-js-sdk DeployParams + ExecutableDeployItem)
        deployHash = await this.submitVaultOpenDeploy(
          params.subscriberAddress,
          motes,
          params.lockBlocks ?? 0,
          keyPair
        );
      }

      return {
        success: true,
        deployHash,
        escrowBalanceMotes: motes.toString(),
        queryPriceMotes: queryPrice.toString(),
        expectedQueries: Math.floor(motes / queryPrice),
        paymentRequest,
      };
    } catch (e) {
      return {
        success: false,
        escrowBalanceMotes: '0',
        queryPriceMotes: queryPrice.toString(),
        expectedQueries: 0,
        error: e instanceof Error ? e.message : String(e),
      };
    }
  }

  /**
   * Verify an incoming x402 payment proof from a client.
   * Called by the VaultWatch API before serving a premium finding.
   */
  async verifyPayment(proof: PaymentProof): Promise<PaymentVerification> {
    const sdk = await this.loadX402SDK();
    return sdk.verifyPayment(proof);
  }

  /**
   * Submit the SubscriberVault.open_vault() deploy.
   * In production this uses casper-js-sdk to construct + sign the deploy.
   */
  private async submitVaultOpenDeploy(
    subscriberAddress: string,
    amountMotes: number,
    lockBlocks: number,
    keyPair: Keys.AsymmetricKey
  ): Promise<string> {
    const casperClient = new CasperClient(this.nodeUrl);
    const rpc = new CasperServiceByJsonRPC(this.nodeUrl);

    // Build session args for SubscriberVault.open_vault()
    const sessionArgs = {
      subscriber_address: subscriberAddress,
      initial_deposit: amountMotes.toString(),
      lock_blocks: lockBlocks,
      auto_renew: true,
      monthly_spend_limit: '0',
      current_block: (await rpc.getLatestBlockInfo()).block?.header?.height ?? 0,
    };

    // NOTE: This is a simplified deploy construction. The actual production
    // deploy uses ExecutableDeployItem.createModuleBytes with the SubscriberVault
    // session code, or a stored-contract call if the vault is already deployed.
    // See docs/X402_INTEGRATION.md for the full deploy template.

    console.log('[x402] Submitting SubscriberVault.open_vault() deploy', {
      subscriberAddress,
      amountMotes,
      lockBlocks,
      network: this.network,
    });

    // Return a placeholder — in production this is the real deploy hash
    // from account_put_deploy.
    throw new Error(
      'Deploy submission requires a deployed SubscriberVault contract. ' +
      'Set SUBSCRIBER_VAULT_HASH env var after running deploy_contracts_live.py, ' +
      'then use casper-js-sdk to construct the stored-contract call. ' +
      'See docs/X402_INTEGRATION.md §3 for the full code template.'
    );
  }

  /**
   * Get the x402 payment request for a single intelligence query.
   * Used by the VaultWatch API to return HTTP 402 to unsubscribed callers.
   */
  async createQueryPaymentRequest(plan: 'standard' | 'premium' = 'standard'): Promise<PaymentRequest> {
    const sdk = await this.loadX402SDK();
    const amount = PLAN_PRICES[plan];
    return sdk.createPaymentRequest({
      payTo: process.env.SENTINEL_CREDIT_HASH ?? '<deploy-and-set-env>',
      payAmount: amount.toString(),
      network: this.network === 'testnet' ? 'casper-test' : 'casper',
      paymentType: 'direct',
      expiresAt: Math.floor(Date.now() / 1000) + 300, // 5 min
      memo: `VaultWatch ${plan} intelligence query`,
    });
  }
}

// Default export
export default VaultWatchX402;

// Example usage (run with: npx tsx x402/vaultwatch-x402.ts)
if (require.main === module) {
  (async () => {
    const x402 = new VaultWatchX402({ network: 'testnet' });
    console.log('[demo] Creating x402 payment request for a standard query…');
    try {
      const req = await x402.createQueryPaymentRequest('standard');
      console.log(JSON.stringify(req, null, 2));
    } catch (e) {
      console.error('[demo] Expected (SDK not installed in demo):', e instanceof Error ? e.message : e);
    }
  })();
}
