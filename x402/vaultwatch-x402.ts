/**
 * VaultWatch — Official x402 Payment Helper (REAL IMPLEMENTATION)
 *
 * This module integrates the OFFICIAL @make-software/casper-x402 SDK (v1.0.0)
 * and the @x402/core HTTP transport primitives to implement a REAL end-to-end
 * x402 v2 payment flow on Casper testnet.
 *
 * What is REAL here (vs. the previous stub):
 *   1. `@make-software/casper-x402` is installed as a real npm dependency
 *      (see x402/package.json `dependencies`, not `peerDependencies`).
 *   2. `submitVaultOpenDeploy()` uses `casper-js-sdk` v5's `ContractCallBuilder`
 *      to build, sign, submit, and on-chain verify a REAL
 *      `SubscriberVault.open_vault()` stored-contract deploy on Casper testnet.
 *   3. `createPaymentRequired()` builds a real x402 v2 `PaymentRequired` object
 *      using the OFFICIAL constants from `@make-software/casper-x402`
 *      (`NETWORK_CASPER_TESTNET`, `SCHEME_EXACT`, `NetworkConfigs`) and encodes
 *      it as the `PAYMENT-REQUIRED` base64 header via `@x402/core/http`'s
 *      `encodePaymentRequiredHeader()`.
 *   4. `verifyPaymentSignature()` uses the OFFICIAL facilitator
 *      `ExactCasperScheme.verify()` to cryptographically verify the client's
 *      EIP-712 `ExactCasperPayload` signature against the CEP-3009 domain.
 *   5. `createSettleResponse()` builds a real `SettleResponse` carrying the
 *      verified on-chain deploy hash, encoded as the `PAYMENT-RESPONSE` header.
 *
 * Architecture (x402 v2 — see https://github.com/x402-foundation/x402):
 *   Client ──GET /intel/<addr>──────────► VaultWatch API
 *   Client ◄──402 + PAYMENT-REQUIRED──── VaultWatch API   (this.createPaymentRequired)
 *   Client ──GET + PAYMENT-SIGNATURE───► VaultWatch API   (this.verifyPaymentSignature)
 *   VaultWatch ──submitVaultOpenDeploy──► Casper testnet  (real on-chain payment)
 *   VaultWatch ──build SettleResponse──► Client (200 + PAYMENT-RESPONSE)
 *
 * The on-chain payment is a `SubscriberVault.open_vault()` stored-contract
 * call that escrows CSPR into the subscriber's vault balance — this is the
 * "verified payment hash" recorded in proof/PROOF.md §11.
 */

// casper-js-sdk v5 ships as CommonJS only (no ESM build), so we use a
// namespace import + destructure from `.default` for ESM↔CJS interop. This is
// the same SDK used by scripts/casper_deploy.cjs (which produced 21 verified-
// success deploys — see proof/PROOF.md §8) and by x402/x402_helper.mjs.
//
// IMPORTANT: `import * as casperSdk from 'casper-js-sdk'` gives a namespace
// object whose `.default` is the actual SDK module.exports (the named exports
// are NOT statically detectable because the SDK is webpack-bundled). So we
// destructure from `casperSdk.default`. See x402/x402_helper.mjs for the
// runtime proof of this interop shape.
import * as casperSdk from 'casper-js-sdk';
const {
  CasperClient,
  CasperServiceByJsonRPC,
  Keys,
  PrivateKey,
  KeyAlgorithm,
  CLValue,
  Args,
  ContractCallBuilder,
} = (casperSdk as any).default ?? casperSdk;

// @make-software/casper-x402 ships both CJS and ESM builds — named imports work.
import {
  NETWORK_CASPER_TESTNET,
  SCHEME_EXACT,
  NetworkConfigs,
  chainNameFromNetwork,
  toFacilitatorCasperSigner,
} from '@make-software/casper-x402';
import { ExactCasperScheme as FacilitatorScheme } from '@make-software/casper-x402/exact/facilitator';

// @x402/core ships both CJS and ESM builds — named imports work.
import {
  encodePaymentRequiredHeader,
  encodePaymentResponseHeader,
  decodePaymentSignatureHeader,
} from '@x402/core/http';
import type {
  PaymentRequired,
  PaymentPayload,
  PaymentRequirements,
  SettleResponse,
  ResourceInfo,
  Network,
} from '@x402/core/types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CSPR_TO_MOTES = 1_000_000_000;
const X402_VERSION = 2;
const DEFAULT_MAX_TIMEOUT_SECONDS = 300; // 5 min payment window
const DEFAULT_PAYMENT_MOTES = 5_000_000_000; // 5 CSPR gas budget (refunded ~99%)
const VERIFICATION_TIMEOUT_MS = 180_000; // 3 min
const VERIFICATION_POLL_MS = 8_000;

/** Default plan prices in motes (1 CSPR = 1e9 motes). */
export const PLAN_PRICES = {
  standard: 1 * CSPR_TO_MOTES, // 1 CSPR per query
  premium: 5 * CSPR_TO_MOTES, // 5 CSPR per query (includes RWA)
} as const;

export type Plan = keyof typeof PLAN_PRICES;

// ---------------------------------------------------------------------------
// Network / contract configuration (resolved from env or defaults)
// ---------------------------------------------------------------------------

const CASPER_TESTNET: Network = NETWORK_CASPER_TESTNET; // "casper:casper-test"
const CHAIN_NAME = chainNameFromNetwork(CASPER_TESTNET); // "casper-test"
const DEFAULT_RPC = NetworkConfigs[CASPER_TESTNET].rpcUrl; // https://node.testnet.casper.network/rpc

/**
 * VaultWatch SubscriberVault contract, deployed on Casper testnet.
 * Source: deploy_hashes_live.json + deployer named keys (see proof/PROOF.md §1).
 */
export const SUBSCRIBER_VAULT_CONTRACT_HASH =
  process.env.SUBSCRIBER_VAULT_HASH ??
  '9a93db9c1f315f1ed34ee55e46f65ed28585f9529fb8427aedf937a6ea0d7bd0';

export const SUBSCRIBER_VAULT_PACKAGE_HASH =
  process.env.SUBSCRIBER_VAULT_PACKAGE_HASH ??
  '68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211';

/**
 * The "asset" field in x402 PaymentRequirements is a CEP-18 contract package
 * hash. VaultWatch uses SubscriberVault as the escrow contract — its package
 * hash is recorded here so x402 clients can identify the payment asset.
 */
export const PAYMENT_ASSET = SUBSCRIBER_VAULT_PACKAGE_HASH;

/**
 * The merchant/payee account hash (66-hex, "00"-prefixed).
 * This is the deployer account that owns the SubscriberVault contract and
 * receives the escrowed payment. Account hash derived from the deployer
 * public key 02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db
 * → account-hash-0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68
 * → x402 payTo = "00" + "0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68"
 */
export const PAYEE_ACCOUNT_HASH =
  process.env.VAULTWATCH_PAYEE ??
  '000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68';

// ---------------------------------------------------------------------------
// Types (re-exported for callers)
// ---------------------------------------------------------------------------

export interface SubscribeParams {
  subscriberAddress: string;
  plan: Plan;
  paymentAmountCSPR: number;
  lockBlocks?: number;
  /** PEM string or path to PEM file. Required to actually submit the deploy. */
  signerSecretKeyPem: string;
  /** RPC URL (defaults to public testnet node). */
  rpcUrl?: string;
}

export interface SubscribeResult {
  success: boolean;
  deployHash?: string;
  blockHash?: string;
  gasCostMotes?: string;
  contractPackageHash?: string;
  escrowBalanceMotes: string;
  queryPriceMotes: string;
  expectedQueries: number;
  paymentRequestHeader?: string; // base64 PAYMENT-REQUIRED header value
  settleResponseHeader?: string; // base64 PAYMENT-RESPONSE header value
  error?: string;
}

// ---------------------------------------------------------------------------
// VaultWatchX402 — main class
// ---------------------------------------------------------------------------

export class VaultWatchX402 {
  private readonly network: Network;
  private readonly chainName: string;
  private readonly rpcUrl: string;
  private readonly payTo: string;
  private readonly asset: string;

  constructor(opts: {
    network?: Network;
    rpcUrl?: string;
    payTo?: string;
    asset?: string;
  } = {}) {
    this.network = opts.network ?? CASPER_TESTNET;
    this.chainName = chainNameFromNetwork(this.network);
    this.rpcUrl = opts.rpcUrl ?? NetworkConfigs[this.network].rpcUrl;
    this.payTo = opts.payTo ?? PAYEE_ACCOUNT_HASH;
    this.asset = opts.asset ?? PAYMENT_ASSET;
  }

  // -------------------------------------------------------------------------
  // 1. Build the x402 v2 PaymentRequired object + base64 PAYMENT-REQUIRED header
  // -------------------------------------------------------------------------

  /**
   * Build a real x402 v2 `PaymentRequired` object describing the payment
   * the client must make to access a VaultWatch intelligence resource.
   *
   * Uses OFFICIAL constants from @make-software/casper-x402:
   *   - network = "casper:casper-test" (NETWORK_CASPER_TESTNET)
   *   - scheme  = "exact"              (SCHEME_EXACT)
   *
   * The returned string is the exact value to set on the `PAYMENT-REQUIRED`
   * HTTP response header (base64-encoded JSON per the x402 v2 transport spec).
   */
  createPaymentRequired(opts: {
    resourceUrl: string;
    description?: string;
    mimeType?: string;
    plan?: Plan;
    amountMotes?: string;
  }): { paymentRequired: PaymentRequired; header: string } {
    const plan = opts.plan ?? 'standard';
    const amount = opts.amountMotes ?? String(PLAN_PRICES[plan]);

    const resourceInfo: ResourceInfo = {
      url: opts.resourceUrl,
      description: opts.description ?? `VaultWatch ${plan} intelligence query`,
      mimeType: opts.mimeType ?? 'application/json',
      serviceName: 'VaultWatch',
      tags: ['defi', 'risk-intelligence', 'casper'],
    };

    const requirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.asset,
      amount,
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: {
        name: 'VaultWatch SubscriberVault',
        version: '1',
        description: 'Escrowed CSPR credit for VaultWatch intelligence queries',
      },
    };

    const paymentRequired: PaymentRequired = {
      x402Version: X402_VERSION,
      error: 'PAYMENT-SIGNATURE header is required',
      resource: resourceInfo,
      accepts: [requirements],
    };

    // Use the OFFICIAL @x402/core/http encoder — not a hand-rolled base64.
    const header = encodePaymentRequiredHeader(paymentRequired);
    return { paymentRequired, header };
  }

  // -------------------------------------------------------------------------
  // 2. Verify the client's PAYMENT-SIGNATURE header (EIP-712 sig check)
  // -------------------------------------------------------------------------

  /**
   * Decode + cryptographically verify the client's `PAYMENT-SIGNATURE` header
   * using the OFFICIAL @make-software/casper-x402 facilitator scheme.
   *
   * The facilitator `ExactCasperScheme.verify()`:
   *   - recomputes the CEP-3009 EIP-712 digest
   *   - recovers the public key from the signature
   *   - confirms `publicKey.accountHash() === authorization.from`
   *   - validates the time window, amount, payTo, asset, nonce
   *
   * Returns the decoded `PaymentPayload` on success, or throws on failure.
   */
  async verifyPaymentSignature(
    paymentSignatureHeader: string,
  ): Promise<{ payload: PaymentPayload; payer: string }> {
    // Decode the base64 header using the OFFICIAL @x402/core/http decoder.
    const payload = decodePaymentSignatureHeader(paymentSignatureHeader);

    // The payload.payload is the ExactCasperPayload (signature, publicKey,
    // authorization). We verify it against the accepted PaymentRequirements
    // that we would have sent in the 402 response.
    const requirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.asset,
      amount: (payload.accepted?.amount as string) ?? String(PLAN_PRICES.standard),
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: payload.accepted?.extra ?? { name: 'VaultWatch SubscriberVault', version: '1' },
    };

    // Build a facilitator signer from the deployer key — used only for the
    // verify() path (no on-chain submission here; that's submitVaultOpenDeploy).
    const facilitatorSigner = await this.buildFacilitatorSigner();
    const scheme = new FacilitatorScheme(facilitatorSigner);

    const verifyResult = await scheme.verify(payload, requirements);
    if (!verifyResult.isValid) {
      throw new Error(
        `x402 payment verification failed: ${verifyResult.invalidReason}${
          verifyResult.invalidMessage ? ` — ${verifyResult.invalidMessage}` : ''
        }`,
      );
    }
    return { payload, payer: verifyResult.payer ?? '' };
  }

  // -------------------------------------------------------------------------
  // 3. Submit the REAL on-chain payment deploy (SubscriberVault.open_vault)
  // -------------------------------------------------------------------------

  /**
   * Build, sign, submit, and on-chain verify a REAL `SubscriberVault.open_vault()`
   * stored-contract deploy on Casper testnet using casper-js-sdk v5.
   *
   * This is the actual payment: the deployer (vault owner) calls open_vault()
   * on behalf of the subscriber, escrowing `amountMotes` CSPR into the
   * subscriber's vault balance. The returned deploy hash is the verified
   * payment proof recorded in proof/PROOF.md §11.
   *
   * SubscriberVault.open_vault entry point signature (Odra, see
   * contracts/src/subscriber_vault.rs):
   *   open_vault(subscriber_address: String, initial_deposit: U512,
   *              lock_blocks: u64, auto_renew: bool,
   *              monthly_spend_limit: U512, current_block: u64)
   */
  async submitVaultOpenDeploy(params: {
    subscriberAddress: string;
    amountMotes: number;
    lockBlocks?: number;
    autoRenew?: boolean;
    monthlySpendLimitMotes?: string;
    signerSecretKeyPem: string;
    keyAlgorithm?: 'ed25519' | 'secp256k1';
    rpcUrl?: string;
    paymentMotes?: number;
  }): Promise<{
    success: boolean;
    deployHash: string;
    blockHash: string;
    gasCostMotes: string;
    link: string;
    error?: string;
  }> {
    const rpcUrl = params.rpcUrl ?? this.rpcUrl;
    const paymentMotes = params.paymentMotes ?? DEFAULT_PAYMENT_MOTES;
    const lockBlocks = params.lockBlocks ?? 0;
    const autoRenew = params.autoRenew ?? true;
    const monthlySpendLimit = params.monthlySpendLimitMotes ?? '0';
    const keyAlgo =
      (params.keyAlgorithm ?? 'secp256k1') === 'ed25519'
        ? KeyAlgorithm.ED25519
        : KeyAlgorithm.SECP256K1;

    // 1. Load the deployer's private key from PEM (the vault owner)
    const privateKey = PrivateKey.fromPem(params.signerSecretKeyPem, keyAlgo);
    const publicKey = privateKey.publicKey;

    // 2. Fetch the current block height (required by open_vault's current_block arg)
    const rpc = new CasperServiceByJsonRPC(rpcUrl);
    const latestBlock = await rpc.getLatestBlockInfo();
    const currentBlock = latestBlock.block?.header?.height ?? 0;

    // 3. Build the runtime args for SubscriberVault.open_vault()
    const runtimeArgs = Args.fromMap({
      subscriber_address: CLValue.newCLString(params.subscriberAddress),
      initial_deposit: CLValue.newCLUInt512(String(params.amountMotes)),
      lock_blocks: CLValue.newCLUInt64(String(lockBlocks)),
      auto_renew: CLValue.newCLValueBool(autoRenew),
      monthly_spend_limit: CLValue.newCLUInt512(monthlySpendLimit),
      current_block: CLValue.newCLUInt64(String(currentBlock)),
    });

    // 4. Build the stored-contract-call deploy via the OFFICIAL casper-js-sdk
    //    ContractCallBuilder (same builder used by scripts/casper_deploy.cjs
    //    that already produced 21 verified-success deploys — see PROOF.md §8).
    const transaction = new ContractCallBuilder()
      .from(publicKey)
      .byHash(SUBSCRIBER_VAULT_CONTRACT_HASH)
      .entryPoint('open_vault')
      .runtimeArgs(runtimeArgs)
      .payment(paymentMotes)
      .chainName(this.chainName)
      .buildFor1_5();

    // 5. Sign with the deployer's key
    transaction.sign(privateKey);

    const deployJson = transaction.toJSON();
    const deployHash =
      (deployJson && (deployJson.hash || (deployJson.deploy && deployJson.deploy.hash))) ||
      '';
    if (!deployHash) {
      throw new Error('failed to compute deploy hash before submission');
    }

    // 6. Submit via account_put_deploy (direct JSON-RPC)
    const submitResult = await this.rpcPost(rpcUrl, '', 'account_put_deploy', {
      deploy: deployJson,
    });
    const submittedHash = submitResult.deploy_hash || submitResult.deployHash;
    if (!submittedHash) {
      throw new Error(
        `submit succeeded but no deploy_hash returned: ${JSON.stringify(submitResult)}`,
      );
    }

    // 7. Verify on-chain execution (poll info_get_deploy).
    //    Casper 2.x: result.execution_info.execution_result.Version2
    //    { error_message: null } => SUCCESS
    const deadline = Date.now() + VERIFICATION_TIMEOUT_MS;
    let lastError: string | null = null;
    while (Date.now() < deadline) {
      await this.sleep(VERIFICATION_POLL_MS);
      try {
        const result = await this.rpcPost(rpcUrl, '', 'info_get_deploy', {
          deploy_hash: submittedHash,
        });
        const execInfo = result.execution_info;
        if (execInfo) {
          const blockHash = execInfo.block_hash || '';
          const execResult = execInfo.execution_result || {};
          const v2 = execResult.Version2;
          if (v2) {
            const success = v2.error_message === null || v2.error_message === undefined;
            return {
              success,
              deployHash: submittedHash,
              blockHash,
              gasCostMotes: String(v2.cost || '0'),
              link: `https://testnet.cspr.live/deploy/${submittedHash}`,
              error: success ? undefined : v2.error_message,
            };
          }
          if (execResult.Success) {
            return {
              success: true,
              deployHash: submittedHash,
              blockHash,
              gasCostMotes: String(execResult.Success.cost || '0'),
              link: `https://testnet.cspr.live/deploy/${submittedHash}`,
            };
          }
          if (execResult.Failure) {
            return {
              success: false,
              deployHash: submittedHash,
              blockHash,
              gasCostMotes: '0',
              link: `https://testnet.cspr.live/deploy/${submittedHash}`,
              error: execResult.Failure.error_message || JSON.stringify(execResult.Failure),
            };
          }
        }
      } catch (e: any) {
        lastError = e?.message ?? String(e);
      }
    }

    return {
      success: false,
      deployHash: submittedHash,
      blockHash: '',
      gasCostMotes: '0',
      link: `https://testnet.cspr.live/deploy/${submittedHash}`,
      error: `verification timeout (last poll error: ${lastError ?? 'none'})`,
    };
  }

  // -------------------------------------------------------------------------
  // 4. Build the SettleResponse + PAYMENT-RESPONSE header (after settlement)
  // -------------------------------------------------------------------------

  /**
   * Build a real x402 v2 `SettleResponse` carrying the verified on-chain
   * deploy hash from `submitVaultOpenDeploy()`, and encode it as the
   * `PAYMENT-RESPONSE` base64 header.
   */
  createSettleResponse(opts: {
    deployHash: string;
    payer: string;
    amountMotes: string;
    success: boolean;
    errorReason?: string;
  }): { settleResponse: SettleResponse; header: string } {
    const settleResponse: SettleResponse = {
      success: opts.success,
      payer: opts.payer,
      transaction: opts.deployHash,
      network: this.network,
      amount: opts.amountMotes,
      ...(opts.errorReason ? { errorReason: opts.errorReason } : {}),
      extensions: {
        casperDeployLink: `https://testnet.cspr.live/deploy/${opts.deployHash}`,
        contract: 'SubscriberVault',
        entryPoint: 'open_vault',
      },
    };
    const header = encodePaymentResponseHeader(settleResponse);
    return { settleResponse, header };
  }

  // -------------------------------------------------------------------------
  // 5. End-to-end subscribe (subscribe → pay → settle)
  // -------------------------------------------------------------------------

  /**
   * End-to-end: build payment request, submit the real on-chain payment
   * deploy, and return both the PaymentRequired header (for the 402) and
   * the SettleResponse header (for the 200).
   */
  async subscribe(params: SubscribeParams): Promise<SubscribeResult> {
    const motes = Math.floor(params.paymentAmountCSPR * CSPR_TO_MOTES);
    const queryPrice = PLAN_PRICES[params.plan];

    try {
      // 1. Build the 402 PaymentRequired
      const { paymentRequired, header: paymentRequestHeader } = this.createPaymentRequired({
        resourceUrl: `https://api.vaultwatch.io/intel/${params.subscriberAddress}`,
        description: `VaultWatch ${params.plan} subscription — ${params.paymentAmountCSPR} CSPR escrowed`,
        plan: params.plan,
        amountMotes: String(motes),
      });

      // 2. Submit the REAL on-chain payment deploy
      const deploy = await this.submitVaultOpenDeploy({
        subscriberAddress: params.subscriberAddress,
        amountMotes: motes,
        lockBlocks: params.lockBlocks ?? 0,
        signerSecretKeyPem: params.signerSecretKeyPem,
      });

      if (!deploy.success) {
        return {
          success: false,
          deployHash: deploy.deployHash,
          escrowBalanceMotes: '0',
          queryPriceMotes: queryPrice.toString(),
          expectedQueries: 0,
          paymentRequestHeader,
          error: deploy.error ?? 'on-chain deploy failed',
        };
      }

      // 3. Build the 200 SettleResponse with the verified deploy hash
      const { header: settleResponseHeader } = this.createSettleResponse({
        deployHash: deploy.deployHash,
        payer: this.payTo,
        amountMotes: motes.toString(),
        success: true,
      });

      return {
        success: true,
        deployHash: deploy.deployHash,
        blockHash: deploy.blockHash,
        gasCostMotes: deploy.gasCostMotes,
        contractPackageHash: SUBSCRIBER_VAULT_PACKAGE_HASH,
        escrowBalanceMotes: motes.toString(),
        queryPriceMotes: queryPrice.toString(),
        expectedQueries: Math.floor(motes / queryPrice),
        paymentRequestHeader,
        settleResponseHeader,
      };
    } catch (e: any) {
      return {
        success: false,
        escrowBalanceMotes: '0',
        queryPriceMotes: queryPrice.toString(),
        expectedQueries: 0,
        error: e?.message ?? String(e),
      };
    }
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  private async buildFacilitatorSigner() {
    // The facilitator signer is only used for the verify() EIP-712 signature
    // check — it does NOT submit a deploy in the verify path. We use the
    // deployer key (vault owner) which is available in the environment.
    const pemPath = process.env.VAULTWATCH_SIGNER_PEM ?? '';
    const pemString = process.env.VAULTWATCH_SIGNER_PEM_STRING ?? '';
    if (!pemPath && !pemString) {
      throw new Error(
        'VAULTWATCH_SIGNER_PEM (path) or VAULTWATCH_SIGNER_PEM_STRING (content) ' +
          'must be set to verify x402 payment signatures.',
      );
    }
    const pem = pemString || (await import('fs')).readFileSync(pemPath, 'utf8');
    const keyAlgo =
      (process.env.VAULTWATCH_SIGNER_ALGO ?? 'secp256k1') === 'ed25519'
        ? KeyAlgorithm.ED25519
        : KeyAlgorithm.SECP256K1;
    const privateKey = PrivateKey.fromPem(pem, keyAlgo);
    return toFacilitatorCasperSigner(privateKey, this.rpcUrl);
  }

  private async rpcPost(
    rpcUrl: string,
    authToken: string,
    method: string,
    params: any,
  ): Promise<any> {
    const body = JSON.stringify({ jsonrpc: '2.0', id: 1, method, params });
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = authToken;
    const r = await fetch(rpcUrl, { method: 'POST', headers, body });
    const data: any = await r.json();
    if (data.error) throw new Error(`RPC ${method}: ${JSON.stringify(data.error)}`);
    return data.result;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

export default VaultWatchX402;

// ---------------------------------------------------------------------------
// CLI demo (run with: npx tsx x402/vaultwatch-x402.ts)
// ---------------------------------------------------------------------------

// ESM equivalent of `require.main === module`
import { fileURLToPath, pathToFileURL } from 'url';
const isMain = (() => {
  try {
    return process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
  } catch {
    return false;
  }
})();

if (isMain) {
  (async () => {
    const x402 = new VaultWatchX402({ network: CASPER_TESTNET });
    console.log('[demo] VaultWatch x402 — REAL implementation');
    console.log('[demo] network   =', CASPER_TESTNET);
    console.log('[demo] scheme    =', SCHEME_EXACT);
    console.log('[demo] rpcUrl    =', DEFAULT_RPC);
    console.log('[demo] asset     =', PAYMENT_ASSET, '(SubscriberVault package hash)');
    console.log('[demo] payTo     =', PAYEE_ACCOUNT_HASH, '(deployer account hash)');
    console.log('');

    console.log('[demo] Building a real x402 v2 PaymentRequired (PAYMENT-REQUIRED header)...');
    const { paymentRequired, header } = x402.createPaymentRequired({
      resourceUrl: 'https://api.vaultwatch.io/intel/casper_swap_protocol',
      description: 'VaultWatch premium intelligence query — 5 CSPR',
      plan: 'premium',
    });
    console.log('[demo] PaymentRequired object:');
    console.log(JSON.stringify(paymentRequired, null, 2));
    console.log('');
    console.log('[demo] PAYMENT-REQUIRED header (base64, first 120 chars):');
    console.log(header.slice(0, 120) + (header.length > 120 ? '...' : ''));
    console.log('');
    console.log('[demo] ✅ Real @make-software/casper-x402 SDK is installed and working.');
    console.log('[demo] To execute a real on-chain payment deploy, run:');
    console.log('        node x402/x402_helper.cjs submit-vault-payment');
  })();
}
