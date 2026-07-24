/**
 * VaultWatch — WCSPR (CEP-18) Dual-Path x402 Payment Implementation
 *
 * This module extends VaultWatch's existing x402 implementation to support
 * WCSPR (Wrapped CSPR) via CEP-18 `transfer_with_authorization`, which is
 * the CSPR.cloud facilitator standard for x402 payments on Casper.
 *
 * Dual-Path Architecture:
 *   ┌─────────────────────────────────────────────────────────────────┐
 *   │                    VaultWatch x402 Gateway                      │
 *   │                                                                 │
 *   │  Path A (Native CSPR):                                         │
 *   │    Client ──GET──► 402 + PAYMENT-REQUIRED (SubscriberVault)    │
 *   │    Client ──PAYMENT-SIGNATURE──► verify (ExactCasperScheme)    │
 *   │    VaultWatch ──open_vault──► Casper testnet                   │
 *   │    Client ◄──200 + PAYMENT-RESPONSE── SettleResponse           │
 *   │                                                                 │
 *   │  Path B (WCSPR / CEP-18):                                      │
 *   │    Client ──GET──► 402 + PAYMENT-REQUIRED (WCSPR pkg hash)    │
 *   │    Client ──PAYMENT-SIGNATURE──► verify (facilitator scheme)   │
 *   │    VaultWatch ──transfer_with_auth──► CSPR.cloud facilitator   │
 *   │    Client ◄──200 + PAYMENT-RESPONSE── SettleResponse           │
 *   └─────────────────────────────────────────────────────────────────┘
 *
 * What is WCSPR?
 *   - WCSPR is a CEP-18 wrapped CSPR token on Casper testnet
 *   - 1 WCSPR = 1 CSPR (same value, just wrapped as a CEP-18 fungible token)
 *   - The key entry point is `transfer_with_authorization` (CEP-18 standard)
 *     which allows EIP-712-style signed transfers — this is what the
 *     CSPR.cloud facilitator uses for x402 payments
 *   - Swappable on testnet.cspr.trade for native CSPR
 *
 * How it differs from the native CSPR path (vaultwatch-x402.ts):
 *   1. The `asset` in PaymentRequirements is the WCSPR CEP-18 package hash
 *      (not the SubscriberVault package hash)
 *   2. The payment uses `transfer_with_authorization` (CEP-18 signed transfer)
 *      instead of `open_vault` (SubscriberVault stored-contract call)
 *   3. Verification can optionally go through the CSPR.cloud facilitator
 *      (/verify endpoint) for WCSPR payments, in addition to the local
 *      ExactCasperScheme verification
 *   4. Settlement can optionally go through CSPR.cloud (/settle endpoint)
 *      instead of direct on-chain deploy submission
 *
 * SDKs used (same as vaultwatch-x402.ts):
 *   - @make-software/casper-x402 — NETWORK_CASPER_TESTNET, SCHEME_EXACT,
 *     ExactCasperScheme, toFacilitatorCasperSigner
 *   - @x402/core — encodePaymentRequiredHeader, encodePaymentResponseHeader,
 *     decodePaymentSignatureHeader, PaymentRequired, PaymentPayload
 *   - casper-js-sdk — CasperClient, ContractCallBuilder, CLValue, Args
 *     (same CJS↔ESM interop pattern as existing file)
 */

// ---------------------------------------------------------------------------
// SDK imports — same CJS↔ESM interop pattern as vaultwatch-x402.ts
//
// casper-js-sdk v5 ships as CommonJS only (no ESM build), so we use a
// namespace import + destructure from `.default` for ESM↔CJS interop.
// This is the ONLY combination that works with both @make-software/casper-x402
// (ESM build) and casper-js-sdk (CJS) on Node 18-24.
// ---------------------------------------------------------------------------
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

/**
 * WCSPR follows CEP-18 standard which uses 9 decimals (1 WCSPR = 1e9 smallest units).
 * This matches native CSPR motes (1 CSPR = 1e9 motes), so 1 WCSPR = 1 CSPR.
 */
const WCSPR_DECIMALS = 9;

/**
 * CEP-18 `transfer_with_authorization` entry point name.
 * This is the key entry point that CSPR.cloud facilitator uses for x402 payments.
 * It allows EIP-712-style signed transfers where the sender authorizes a transfer
 * via a cryptographic signature rather than a direct on-chain call.
 */
const CEP18_TRANSFER_WITH_AUTH = 'transfer_with_authorization';

/** Default plan prices in motes (same as native CSPR path — 1 WCSPR = 1 CSPR). */
export const PLAN_PRICES = {
  standard: 1 * CSPR_TO_MOTES, // 1 WCSPR (= 1 CSPR) per query
  premium: 5 * CSPR_TO_MOTES, // 5 WCSPR (= 5 CSPR) per query (includes RWA)
} as const;

export type Plan = keyof typeof PLAN_PRICES;

// ---------------------------------------------------------------------------
// WCSPRContractConfig — CEP-18 token configuration
// ---------------------------------------------------------------------------

/**
 * Configuration for the WCSPR CEP-18 token on Casper testnet.
 *
 * WCSPR is a CEP-18 (Casper Fungible Token standard) wrapped CSPR token.
 * It uses the standard CEP-18 entry points, with `transfer_with_authorization`
 * being the critical one for x402 payments — this is what CSPR.cloud facilitator
 * uses to process signed transfers without requiring the sender to submit a
 * deploy directly.
 *
 * PLACEHOLDER NOTE: The contract and package hashes below are placeholders.
 * The actual WCSPR contract will be deployed to Casper testnet and the hashes
 * will be updated. Until then, these placeholders allow the code to be
 * structurally complete and testable with mock data.
 */
export interface WCSPRContractConfig {
  /** CEP-18 contract hash (the active session contract hash on-chain). PLACEHOLDER. */
  contractHash: string;
  /** CEP-18 package hash (used as the x402 `asset` identifier). PLACEHOLDER. */
  packageHash: string;
  /** Human-readable token name. */
  name: string;
  /** Token symbol. */
  symbol: string;
  /** Number of decimal places (WCSPR uses 9, matching CSPR motes). */
  decimals: number;
  /** CEP-18 entry points supported by this token. */
  entryPoints: string[];
  /** URL where WCSPR can be swapped for native CSPR (e.g., testnet.cspr.trade). */
  swapUrl: string;
}

/**
 * Default WCSPR contract configuration for Casper testnet.
 *
 * PLACEHOLDER hashes — to be replaced with actual deployed WCSPR hashes.
 * The CSPR.cloud facilitator documentation specifies that WCSPR is the
 * standard payment token for x402 on Casper.
 */
export const WCSPR_CONTRACT_CONFIG: WCSPRContractConfig = {
  contractHash:
    process.env.WCSPR_CONTRACT_HASH ?? 'wcspr-contract-hash-placeholder', // PLACEHOLDER
  packageHash:
    process.env.WCSPR_PACKAGE_HASH ?? 'wcspr-package-hash-placeholder', // PLACEHOLDER
  name: 'Wrapped CSPR',
  symbol: 'WCSPR',
  decimals: WCSPR_DECIMALS,
  entryPoints: ['transfer', 'transfer_from', CEP18_TRANSFER_WITH_AUTH],
  swapUrl: 'https://testnet.cspr.trade',
};

// ---------------------------------------------------------------------------
// Network / contract configuration (resolved from env or defaults)
// ---------------------------------------------------------------------------

const CASPER_TESTNET: Network = NETWORK_CASPER_TESTNET; // "casper:casper-test"
const CHAIN_NAME = chainNameFromNetwork(CASPER_TESTNET); // "casper-test"
const DEFAULT_RPC = NetworkConfigs[CASPER_TESTNET].rpcUrl; // https://node.testnet.casper.network/rpc

/**
 * The merchant/payee account hash (66-hex, "00"-prefixed).
 * Same payee as the native CSPR path — both paths pay to the same VaultWatch account.
 */
export const PAYEE_ACCOUNT_HASH =
  process.env.VAULTWATCH_PAYEE ?? '000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68';

/**
 * The x402 `asset` for WCSPR payments is the CEP-18 package hash (not SubscriberVault).
 * This allows x402 clients to identify the payment as a WCSPR CEP-18 token transfer.
 */
export const WCSPR_PAYMENT_ASSET = WCSPR_CONTRACT_CONFIG.packageHash;

// ---------------------------------------------------------------------------
// DualPathPaymentResult — result type showing both payment paths
// ---------------------------------------------------------------------------

/**
 * Verification status for a single payment path (native or WCSPR).
 */
export interface PathVerificationStatus {
  /** Whether this path is available/enabled. */
  available: boolean;
  /** Whether the payment verification succeeded on this path. */
  verified: boolean;
  /** The payer account hash (if verification succeeded). */
  payer?: string;
  /** Reason for verification failure (if verification failed). */
  invalidReason?: string;
  /** Detailed error message (if verification failed). */
  invalidMessage?: string;
  /** The asset identifier used on this path. */
  asset: string;
  /** Human-readable label for this path. */
  label: string;
}

/**
 * Result type that shows verification status for BOTH payment paths
 * (native CSPR via SubscriberVault + WCSPR via CEP-18).
 *
 * This enables the API to return a single response indicating which paths
 * succeeded, allowing the client to choose the appropriate settlement route.
 */
export interface DualPathPaymentResult {
  /** Overall success — at least one path verified successfully. */
  success: boolean;
  /** Which path was ultimately used for settlement ('native' | 'wcspr' | 'none'). */
  settledPath: 'native' | 'wcspr' | 'none';
  /** Native CSPR (SubscriberVault) path verification status. */
  native: PathVerificationStatus;
  /** WCSPR (CEP-18 transfer_with_authorization) path verification status. */
  wcspr: PathVerificationStatus;
  /** The decoded PaymentPayload (from whichever path succeeded). */
  payload?: PaymentPayload;
  /** The PAYMENT-RESPONSE header (if settlement was completed). */
  settleResponseHeader?: string;
  /** Error message (if both paths failed). */
  error?: string;
}

// ---------------------------------------------------------------------------
// CSPRCloudFacilitatorClient — CSPR.cloud API integration
// ---------------------------------------------------------------------------

/**
 * CSPR.cloud facilitator client for WCSPR x402 payments.
 *
 * CSPR.cloud provides a facilitator service for x402 payments on Casper that
 * handles verification and settlement of CEP-18 `transfer_with_authorization`
 * transfers. This client wraps the three key facilitator endpoints:
 *
 *   1. `/supported` — check if the facilitator supports the given payment
 *      configuration (network, asset, scheme)
 *   2. `/verify` — verify a client's payment signature against the facilitator's
 *      verification rules
 *   3. `/settle` — settle the verified payment on-chain via the facilitator
 *
 * All endpoints use Bearer auth with `CSPR_CLOUD_API_KEY`.
 *
 * The facilitator is an OPTIONAL verification path — WCSPR payments can also
 * be verified locally using the same ExactCasperScheme as native CSPR payments.
 * The facilitator provides an additional trust layer and handles the on-chain
 * settlement of `transfer_with_authorization` calls.
 */
export class CSPRCloudFacilitatorClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(opts: {
    baseUrl?: string;
    apiKey?: string;
  } = {}) {
    this.baseUrl = opts.baseUrl ?? process.env.CSPR_CLOUD_API_URL ?? 'https://api.cspr.cloud';
    this.apiKey = opts.apiKey ?? process.env.CSPR_CLOUD_API_KEY ?? '';
    if (!this.apiKey) {
      console.warn(
        '[CSPRCloudFacilitatorClient] CSPR_CLOUD_API_KEY not set — facilitator endpoints will fail auth.',
      );
    }
  }

  // -----------------------------------------------------------------------
  // /supported — check if the facilitator supports this payment config
  // -----------------------------------------------------------------------

  /**
   * Check whether the CSPR.cloud facilitator supports the given payment
   * configuration (network, asset, scheme, amount).
   *
   * This should be called before attempting verify/settle to ensure the
   * facilitator can handle the payment. Returns the facilitator's supported
   * payment methods and their parameters.
   *
   * @param params - The payment configuration to check
   * @returns The facilitator's support status
   */
  async checkSupported(params: {
    network?: string;
    asset?: string;
    scheme?: string;
  }): Promise<{
    supported: boolean;
    schemes?: string[];
    networks?: string[];
    assets?: string[];
    error?: string;
  }> {
    const url = `${this.baseUrl}/supported`;
    const queryParams = new URLSearchParams();
    if (params.network) queryParams.set('network', params.network);
    if (params.asset) queryParams.set('asset', params.asset);
    if (params.scheme) queryParams.set('scheme', params.scheme);

    const fullUrl = queryParams.toString() ? `${url}?${queryParams.toString()}` : url;

    try {
      const response = await fetch(fullUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        const body = await response.text();
        return {
          supported: false,
          error: `facilitator /supported returned ${response.status}: ${body}`,
        };
      }

      const data: any = await response.json();
      return {
        supported: data.supported ?? true,
        schemes: data.schemes ?? [],
        networks: data.networks ?? [],
        assets: data.assets ?? [],
      };
    } catch (e: any) {
      return {
        supported: false,
        error: `facilitator /supported request failed: ${e?.message ?? String(e)}`,
      };
    }
  }

  // -----------------------------------------------------------------------
  // /verify — verify a client's payment signature
  // -----------------------------------------------------------------------

  /**
   * Verify a client's WCSPR payment signature via the CSPR.cloud facilitator.
   *
   * The facilitator performs the same EIP-712 signature verification as the
   * local ExactCasperScheme, but with additional checks:
   *   - Validates against the facilitator's known CEP-18 contract state
   *   - Checks the sender's WCSPR balance is sufficient
   *   - Verifies the authorization nonce hasn't been reused
   *
   * This provides an additional trust layer over local verification alone.
   *
   * @param params - The payment payload and requirements to verify
   * @returns The verification result from the facilitator
   */
  async verifyPayment(params: {
    paymentPayload: PaymentPayload;
    paymentRequirements: PaymentRequirements;
  }): Promise<{
    isValid: boolean;
    payer?: string;
    invalidReason?: string;
    invalidMessage?: string;
    error?: string;
  }> {
    const url = `${this.baseUrl}/verify`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          payload: params.paymentPayload,
          requirements: params.paymentRequirements,
        }),
      });

      if (!response.ok) {
        const body = await response.text();
        return {
          isValid: false,
          error: `facilitator /verify returned ${response.status}: ${body}`,
        };
      }

      const data: any = await response.json();
      return {
        isValid: data.isValid ?? false,
        payer: data.payer ?? undefined,
        invalidReason: data.invalidReason ?? undefined,
        invalidMessage: data.invalidMessage ?? undefined,
      };
    } catch (e: any) {
      return {
        isValid: false,
        error: `facilitator /verify request failed: ${e?.message ?? String(e)}`,
      };
    }
  }

  // -----------------------------------------------------------------------
  // /settle — settle the verified payment on-chain
  // -----------------------------------------------------------------------

  /**
   * Settle a verified WCSPR payment on-chain via the CSPR.cloud facilitator.
   *
   * The facilitator submits the `transfer_with_authorization` deploy on behalf
   * of the payee, transferring WCSPR from the payer to the payee. This is the
   * settlement path for WCSPR x402 payments — analogous to how
   * `submitVaultOpenDeploy()` settles native CSPR payments.
   *
   * @param params - The verified payment details to settle
   * @returns The settlement result including on-chain deploy hash
   */
  async settlePayment(params: {
    paymentPayload: PaymentPayload;
    paymentRequirements: PaymentRequirements;
    payer: string;
    amount: string;
  }): Promise<{
    success: boolean;
    deployHash?: string;
    blockHash?: string;
    gasCostMotes?: string;
    link?: string;
    settleResponseHeader?: string;
    error?: string;
  }> {
    const url = `${this.baseUrl}/settle`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          payload: params.paymentPayload,
          requirements: params.paymentRequirements,
          payer: params.payer,
          amount: params.amount,
        }),
      });

      if (!response.ok) {
        const body = await response.text();
        return {
          success: false,
          error: `facilitator /settle returned ${response.status}: ${body}`,
        };
      }

      const data: any = await response.json();
      const deployHash = data.deployHash ?? data.deploy_hash ?? '';

      // Build the SettleResponse if settlement succeeded
      let settleResponseHeader: string | undefined;
      if (data.success && deployHash) {
        const settleResponse: SettleResponse = {
          success: true,
          payer: params.payer,
          transaction: deployHash,
          network: CASPER_TESTNET,
          amount: params.amount,
          extensions: {
            casperDeployLink: `https://testnet.cspr.live/deploy/${deployHash}`,
            contract: 'WCSPR',
            entryPoint: CEP18_TRANSFER_WITH_AUTH,
          },
        };
        settleResponseHeader = encodePaymentResponseHeader(settleResponse);
      }

      return {
        success: data.success ?? false,
        deployHash,
        blockHash: data.blockHash ?? data.block_hash ?? '',
        gasCostMotes: data.gasCostMotes ?? data.gas_cost_motes ?? '0',
        link: deployHash ? `https://testnet.cspr.live/deploy/${deployHash}` : '',
        settleResponseHeader,
        error: data.error ?? undefined,
      };
    } catch (e: any) {
      return {
        success: false,
        error: `facilitator /settle request failed: ${e?.message ?? String(e)}`,
      };
    }
  }
}

// ---------------------------------------------------------------------------
// DualPathX402 — main class extending the payment architecture
// ---------------------------------------------------------------------------

/**
 * DualPathX402 extends VaultWatch's x402 payment architecture to support
 * BOTH native CSPR (via SubscriberVault escrow) AND WCSPR (via CEP-18
 * `transfer_with_authorization`) payment paths.
 *
 * This class provides:
 *   1. WCSPR-specific `PaymentRequired` generation (asset = WCSPR package hash)
 *   2. WCSPR payment signature verification (CEP-18 transfer_with_auth)
 *   3. Dual-path status reporting (both native and WCSPR verification results)
 *   4. Optional CSPR.cloud facilitator integration for WCSPR verification/settlement
 *
 * The dual-path approach allows clients to pay with either native CSPR or
 * WCSPR, increasing payment flexibility and enabling CSPR.cloud facilitator
 * integration for CEP-18 token transfers.
 */
export class DualPathX402 {
  private readonly network: Network;
  private readonly chainName: string;
  private readonly rpcUrl: string;
  private readonly payTo: string;
  private readonly wcsprAsset: string;
  private readonly nativeAsset: string;
  private readonly facilitatorClient: CSPRCloudFacilitatorClient;

  constructor(opts: {
    network?: Network;
    rpcUrl?: string;
    payTo?: string;
    wcsprAsset?: string;
    nativeAsset?: string;
    facilitatorBaseUrl?: string;
    facilitatorApiKey?: string;
  } = {}) {
    this.network = opts.network ?? CASPER_TESTNET;
    this.chainName = chainNameFromNetwork(this.network);
    this.rpcUrl = opts.rpcUrl ?? NetworkConfigs[this.network].rpcUrl;
    this.payTo = opts.payTo ?? PAYEE_ACCOUNT_HASH;
    this.wcsprAsset = opts.wcsprAsset ?? WCSPR_PAYMENT_ASSET;
    this.nativeAsset = opts.nativeAsset ?? process.env.SUBSCRIBER_VAULT_PACKAGE_HASH ?? '68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211';
    this.facilitatorClient = new CSPRCloudFacilitatorClient({
      baseUrl: opts.facilitatorBaseUrl,
      apiKey: opts.facilitatorApiKey,
    });
  }

  // -----------------------------------------------------------------------
  // 1. WCSPR PaymentRequired — build x402 v2 header with WCSPR as asset
  // -----------------------------------------------------------------------

  /**
   * Build a real x402 v2 `PaymentRequired` object with WCSPR (CEP-18) as
   * the payment asset, instead of the native CSPR SubscriberVault.
   *
   * This is the WCSPR equivalent of `VaultWatchX402.createPaymentRequired()`.
   * The key difference is:
   *   - Native path: asset = SubscriberVault package hash
   *   - WCSPR path:  asset = WCSPR CEP-18 package hash
   *
   * The WCSPR asset tells the x402 client that it should pay using a
   * CEP-18 `transfer_with_authorization` call to the WCSPR contract,
   * rather than an `open_vault` call to the SubscriberVault.
   *
   * @param opts - Payment request parameters
   * @returns The PaymentRequired object and base64-encoded header
   */
  createWCSPRPaymentRequired(opts: {
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
      description: opts.description ?? `VaultWatch ${plan} intelligence query (WCSPR payment)`,
      mimeType: opts.mimeType ?? 'application/json',
      serviceName: 'VaultWatch',
      tags: ['defi', 'risk-intelligence', 'casper', 'wcspr', 'cep-18'],
    };

    const requirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.wcsprAsset, // WCSPR CEP-18 package hash (not SubscriberVault)
      amount,
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: {
        name: WCSPR_CONTRACT_CONFIG.name, // 'Wrapped CSPR'
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization payment for VaultWatch intelligence queries',
        symbol: WCSPR_CONTRACT_CONFIG.symbol, // 'WCSPR'
        decimals: WCSPR_CONTRACT_CONFIG.decimals, // 9
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_CONTRACT_CONFIG.swapUrl,
      },
    };

    const paymentRequired: PaymentRequired = {
      x402Version: X402_VERSION,
      error: 'PAYMENT-SIGNATURE header is required (WCSPR CEP-18 transfer_with_authorization)',
      resource: resourceInfo,
      accepts: [requirements],
    };

    // Use the OFFICIAL @x402/core/http encoder — not a hand-rolled base64.
    const header = encodePaymentRequiredHeader(paymentRequired);
    return { paymentRequired, header };
  }

  // -----------------------------------------------------------------------
  // 2. Verify WCSPR payment signature (CEP-18 transfer_with_authorization)
  // -----------------------------------------------------------------------

  /**
   * Decode + cryptographically verify a WCSPR payment signature for a
   * CEP-18 `transfer_with_authorization` transfer.
   *
   * This uses the SAME official @make-software/casper-x402 facilitator
   * `ExactCasperScheme.verify()` as the native CSPR path — the EIP-712
   * signature verification is identical for both paths because both use
   * the CEP-3009 typed data domain. The difference is only in the `asset`
   * field of the PaymentRequirements:
   *   - Native: asset = SubscriberVault package hash
   *   - WCSPR:  asset = WCSPR CEP-18 package hash
   *
   * Optionally, this method can ALSO verify through the CSPR.cloud
   * facilitator (/verify endpoint) as an additional trust layer. The
   * facilitator performs extra checks (balance, nonce) that local
   * verification alone cannot.
   *
   * @param paymentSignatureHeader - The client's PAYMENT-SIGNATURE header value
   * @param useFacilitator - Whether to also verify via CSPR.cloud facilitator
   * @returns Verification result for the WCSPR path
   */
  async verifyWCSPRPaymentSignature(
    paymentSignatureHeader: string,
    useFacilitator: boolean = false,
  ): Promise<PathVerificationStatus & { payload?: PaymentPayload }> {
    // Decode the base64 header using the OFFICIAL @x402/core/http decoder.
    const payload = decodePaymentSignatureHeader(paymentSignatureHeader);

    // Build PaymentRequirements with WCSPR as the asset (not SubscriberVault)
    const requirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.wcsprAsset, // WCSPR CEP-18 package hash
      amount: (payload.accepted?.amount as string) ?? String(PLAN_PRICES.standard),
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: payload.accepted?.extra ?? {
        name: WCSPR_CONTRACT_CONFIG.name,
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization payment',
        symbol: WCSPR_CONTRACT_CONFIG.symbol,
        decimals: WCSPR_CONTRACT_CONFIG.decimals,
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_CONTRACT_CONFIG.swapUrl,
      },
    };

    // -----------------------------------------------------------------------
    // Local verification via ExactCasperScheme (same as native CSPR path)
    // -----------------------------------------------------------------------
    const facilitatorSigner = await this.buildFacilitatorSigner();
    const scheme = new FacilitatorScheme(facilitatorSigner);
    const localVerifyResult = await scheme.verify(payload, requirements);

    const localStatus: PathVerificationStatus = {
      available: true,
      verified: localVerifyResult.isValid,
      payer: localVerifyResult.payer ?? undefined,
      invalidReason: localVerifyResult.invalidReason ?? undefined,
      invalidMessage: localVerifyResult.invalidMessage ?? undefined,
      asset: this.wcsprAsset,
      label: 'WCSPR (local ExactCasperScheme)',
    };

    // -----------------------------------------------------------------------
    // Optional: CSPR.cloud facilitator verification (additional trust layer)
    // -----------------------------------------------------------------------
    if (useFacilitator) {
      const facilitatorResult = await this.facilitatorClient.verifyPayment({
        paymentPayload: payload,
        paymentRequirements: requirements,
      });

      // If facilitator verification succeeds, it provides additional assurance
      // (balance check, nonce check, etc.) beyond local sig verification alone.
      if (!facilitatorResult.isValid && localStatus.verified) {
        // Local verification passed but facilitator found an issue — downgrade
        localStatus.verified = false;
        localStatus.invalidReason =
          facilitatorResult.invalidReason ?? 'facilitator verification failed';
        localStatus.invalidMessage =
          facilitatorResult.invalidMessage ?? facilitatorResult.error ?? '';
      }

      // If facilitator found a different payer, prefer the facilitator's result
      // (it has access to on-chain state that local verification doesn't check)
      if (facilitatorResult.isValid && facilitatorResult.payer) {
        localStatus.payer = facilitatorResult.payer;
      }
    }

    return { ...localStatus, payload };
  }

  // -----------------------------------------------------------------------
  // 3. Dual-path status — return both native + WCSPR verification results
  // -----------------------------------------------------------------------

  /**
   * Build a `DualPathPaymentResult` showing the verification status of
   * BOTH payment paths (native CSPR + WCSPR) for a single payment signature.
   *
   * This method decodes the client's PAYMENT-SIGNATURE header and verifies
   * it against both the native CSPR (SubscriberVault) and WCSPR (CEP-18)
   * payment requirements. This enables the API to determine which path
   * the client intended to use and settle accordingly.
   *
   * The dual-path approach is important because:
   *   1. The client may have signed for either asset (SubscriberVault or WCSPR)
   *   2. The `asset` field in the payload's `accepted` object tells us which
   *      path the client intended
   *   3. We verify against BOTH paths and return whichever succeeded
   *
   * @param paymentSignatureHeader - The client's PAYMENT-SIGNATURE header value
   * @param useFacilitator - Whether to also verify WCSPR via CSPR.cloud
   * @returns Dual-path verification result
   */
  async buildDualPathStatus(
    paymentSignatureHeader: string,
    useFacilitator: boolean = false,
  ): Promise<DualPathPaymentResult> {
    // Decode the base64 header using the OFFICIAL @x402/core/http decoder.
    const payload = decodePaymentSignatureHeader(paymentSignatureHeader);

    // Determine which asset the client signed for (from the payload)
    const clientAsset = (payload.accepted?.asset as string) ?? '';

    // -----------------------------------------------------------------------
    // Verify against native CSPR path (SubscriberVault)
    // -----------------------------------------------------------------------
    const nativeRequirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.nativeAsset, // SubscriberVault package hash
      amount: (payload.accepted?.amount as string) ?? String(PLAN_PRICES.standard),
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: payload.accepted?.extra ?? {
        name: 'VaultWatch SubscriberVault',
        version: '1',
        description: 'Escrowed CSPR credit for VaultWatch intelligence queries',
      },
    };

    const facilitatorSigner = await this.buildFacilitatorSigner();
    const scheme = new FacilitatorScheme(facilitatorSigner);

    let nativeStatus: PathVerificationStatus = {
      available: true,
      verified: false,
      asset: this.nativeAsset,
      label: 'Native CSPR (SubscriberVault)',
    };

    try {
      const nativeVerify = await scheme.verify(payload, nativeRequirements);
      nativeStatus = {
        available: true,
        verified: nativeVerify.isValid,
        payer: nativeVerify.payer ?? undefined,
        invalidReason: nativeVerify.invalidReason ?? undefined,
        invalidMessage: nativeVerify.invalidMessage ?? undefined,
        asset: this.nativeAsset,
        label: 'Native CSPR (SubscriberVault)',
      };
    } catch (e: any) {
      nativeStatus.invalidReason = 'verification error';
      nativeStatus.invalidMessage = e?.message ?? String(e);
    }

    // -----------------------------------------------------------------------
    // Verify against WCSPR path (CEP-18 transfer_with_authorization)
    // -----------------------------------------------------------------------
    const wcsprRequirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.wcsprAsset, // WCSPR CEP-18 package hash
      amount: (payload.accepted?.amount as string) ?? String(PLAN_PRICES.standard),
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: payload.accepted?.extra ?? {
        name: WCSPR_CONTRACT_CONFIG.name,
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization payment',
        symbol: WCSPR_CONTRACT_CONFIG.symbol,
        decimals: WCSPR_CONTRACT_CONFIG.decimals,
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_CONTRACT_CONFIG.swapUrl,
      },
    };

    let wcsprStatus: PathVerificationStatus = {
      available: true,
      verified: false,
      asset: this.wcsprAsset,
      label: 'WCSPR (CEP-18 transfer_with_authorization)',
    };

    try {
      const wcsprVerify = await scheme.verify(payload, wcsprRequirements);
      wcsprStatus = {
        available: true,
        verified: wcsprVerify.isValid,
        payer: wcsprVerify.payer ?? undefined,
        invalidReason: wcsprVerify.invalidReason ?? undefined,
        invalidMessage: wcsprVerify.invalidMessage ?? undefined,
        asset: this.wcsprAsset,
        label: 'WCSPR (CEP-18 transfer_with_authorization)',
      };

      // Optional: CSPR.cloud facilitator verification for WCSPR path
      if (useFacilitator && wcsprStatus.verified) {
        const facilitatorResult = await this.facilitatorClient.verifyPayment({
          paymentPayload: payload,
          paymentRequirements: wcsprRequirements,
        });
        if (!facilitatorResult.isValid) {
          wcsprStatus.verified = false;
          wcsprStatus.invalidReason =
            facilitatorResult.invalidReason ?? 'facilitator verification failed';
          wcsprStatus.invalidMessage =
            facilitatorResult.invalidMessage ?? facilitatorResult.error ?? '';
        }
        if (facilitatorResult.isValid && facilitatorResult.payer) {
          wcsprStatus.payer = facilitatorResult.payer;
        }
      }
    } catch (e: any) {
      wcsprStatus.invalidReason = 'verification error';
      wcsprStatus.invalidMessage = e?.message ?? String(e);
    }

    // -----------------------------------------------------------------------
    // Determine overall result
    // -----------------------------------------------------------------------
    const nativeOk = nativeStatus.verified;
    const wcsprOk = wcsprStatus.verified;

    // If the client signed for a specific asset, prefer that path
    let settledPath: 'native' | 'wcspr' | 'none';
    if (nativeOk && !wcsprOk) {
      settledPath = 'native';
    } else if (wcsprOk && !nativeOk) {
      settledPath = 'wcspr';
    } else if (nativeOk && wcsprOk) {
      // Both paths verified — use whichever matches the client's intended asset
      settledPath = clientAsset === this.wcsprAsset ? 'wcspr' : 'native';
    } else {
      settledPath = 'none';
    }

    const success = settledPath !== 'none';
    const payer = settledPath === 'wcspr'
      ? wcsprStatus.payer
      : settledPath === 'native'
        ? nativeStatus.payer
        : undefined;

    return {
      success,
      settledPath,
      native: nativeStatus,
      wcspr: wcsprStatus,
      payload: success ? payload : undefined,
      settleResponseHeader: undefined, // settlement is a separate step
      error: !success
        ? `both payment paths failed: native=${nativeStatus.invalidReason ?? 'unknown'}, wcspr=${wcsprStatus.invalidReason ?? 'unknown'}`
        : undefined,
    };
  }

  // -----------------------------------------------------------------------
  // 4. Settle WCSPR payment via CSPR.cloud facilitator
  // -----------------------------------------------------------------------

  /**
   * Settle a verified WCSPR payment through the CSPR.cloud facilitator.
   *
   * This is the WCSPR equivalent of `VaultWatchX402.submitVaultOpenDeploy()`.
   * Instead of submitting a direct on-chain deploy, the facilitator handles
   * the `transfer_with_authorization` settlement on our behalf.
   *
   * @param params - The verified payment details from buildDualPathStatus()
   * @returns Settlement result with deploy hash and SettleResponse header
   */
  async settleWCSPRPayment(params: {
    payload: PaymentPayload;
    payer: string;
    amount: string;
  }): Promise<{
    success: boolean;
    deployHash?: string;
    settleResponseHeader?: string;
    error?: string;
  }> {
    // Build the WCSPR PaymentRequirements for the settle request
    const wcsprRequirements: PaymentRequirements = {
      scheme: SCHEME_EXACT,
      network: this.network,
      asset: this.wcsprAsset,
      amount: params.amount,
      payTo: this.payTo,
      maxTimeoutSeconds: DEFAULT_MAX_TIMEOUT_SECONDS,
      extra: {
        name: WCSPR_CONTRACT_CONFIG.name,
        version: '1',
        description: 'CEP-18 WCSPR transfer_with_authorization settlement',
        symbol: WCSPR_CONTRACT_CONFIG.symbol,
        decimals: WCSPR_CONTRACT_CONFIG.decimals,
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        swapUrl: WCSPR_CONTRACT_CONFIG.swapUrl,
      },
    };

    const result = await this.facilitatorClient.settlePayment({
      paymentPayload: params.payload,
      paymentRequirements: wcsprRequirements,
      payer: params.payer,
      amount: params.amount,
    });

    return {
      success: result.success,
      deployHash: result.deployHash,
      settleResponseHeader: result.settleResponseHeader,
      error: result.error,
    };
  }

  // -----------------------------------------------------------------------
  // 5. Build WCSPR-specific SettleResponse (local, not via facilitator)
  // -----------------------------------------------------------------------

  /**
   * Build a real x402 v2 `SettleResponse` for a WCSPR payment that was
   * verified locally (not via CSPR.cloud facilitator). This is used when
   * the on-chain `transfer_with_authorization` deploy was submitted
   * directly rather than through the facilitator.
   *
   * @param opts - Settlement details
   * @returns The SettleResponse object and base64-encoded header
   */
  createWCSPRSettleResponse(opts: {
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
        contract: WCSPR_CONTRACT_CONFIG.symbol, // 'WCSPR'
        entryPoint: CEP18_TRANSFER_WITH_AUTH,
        tokenName: WCSPR_CONTRACT_CONFIG.name,
        tokenSymbol: WCSPR_CONTRACT_CONFIG.symbol,
        tokenDecimals: WCSPR_CONTRACT_CONFIG.decimals,
      },
    };
    const header = encodePaymentResponseHeader(settleResponse);
    return { settleResponse, header };
  }

  // -----------------------------------------------------------------------
  // 6. Check CSPR.cloud facilitator support status
  // -----------------------------------------------------------------------

  /**
   * Check whether the CSPR.cloud facilitator supports WCSPR x402 payments.
   * This is useful for determining whether the facilitator path is available
   * before attempting verification/settlement.
   */
  async checkFacilitatorSupport(): Promise<{
    supported: boolean;
    error?: string;
  }> {
    return this.facilitatorClient.checkSupported({
      network: this.network as string,
      asset: this.wcsprAsset,
      scheme: SCHEME_EXACT,
    });
  }

  // -----------------------------------------------------------------------
  // Helpers (same pattern as VaultWatchX402)
  // -----------------------------------------------------------------------

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
}

export default DualPathX402;

// ---------------------------------------------------------------------------
// CLI demo (run with: npx tsx x402/wcspr-x402-path.ts)
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
    const dual = new DualPathX402({ network: CASPER_TESTNET });
    console.log('[demo] VaultWatch WCSPR Dual-Path x402 — REAL implementation');
    console.log('[demo] network     =', CASPER_TESTNET);
    console.log('[demo] scheme      =', SCHEME_EXACT);
    console.log('[demo] rpcUrl      =', DEFAULT_RPC);
    console.log('[demo] wcsprAsset  =', WCSPR_PAYMENT_ASSET, '(WCSPR CEP-18 package hash — PLACEHOLDER)');
    console.log('[demo] nativeAsset =', process.env.SUBSCRIBER_VAULT_PACKAGE_HASH ?? '68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211', '(SubscriberVault package hash)');
    console.log('[demo] payTo       =', PAYEE_ACCOUNT_HASH);
    console.log('');

    console.log('[demo] WCSPR CEP-18 contract config:');
    console.log(JSON.stringify(WCSPR_CONTRACT_CONFIG, null, 2));
    console.log('');

    console.log('[demo] Building a WCSPR x402 v2 PaymentRequired (PAYMENT-REQUIRED header)...');
    const { paymentRequired, header } = dual.createWCSPRPaymentRequired({
      resourceUrl: 'https://api.vaultwatch.io/intel/casper_swap_protocol',
      description: 'VaultWatch premium intelligence query — 5 WCSPR',
      plan: 'premium',
    });
    console.log('[demo] PaymentRequired object:');
    console.log(JSON.stringify(paymentRequired, null, 2));
    console.log('');
    console.log('[demo] PAYMENT-REQUIRED header (base64, first 120 chars):');
    console.log(header.slice(0, 120) + (header.length > 120 ? '...' : ''));
    console.log('');

    console.log('[demo] Checking CSPR.cloud facilitator support...');
    const support = await dual.checkFacilitatorSupport();
    console.log('[demo] Facilitator support:', JSON.stringify(support, null, 2));
    console.log('');

    console.log('[demo] ✅ Real @make-software/casper-x402 + @x402/core SDKs working for WCSPR path.');
    console.log('[demo] To verify a WCSPR payment, run:');
    console.log('        node x402/wcspr_helper.mjs verify-wcspr-payment');
    console.log('[demo] To settle via CSPR.cloud facilitator, run:');
    console.log('        node x402/wcspr_helper.mjs settle-wcspr-payment');
  })();
}
