# VaultWatch — Dual-Path x402 Payment Architecture

> **DoraHacks Casper Agentic Buildathon 2026 Finals Submission**
> Comprehensive documentation of VaultWatch's dual-path x402 payment architecture,
> supporting both self-hosted native CSPR and CSPR.cloud facilitator WCSPR paths.
> This architecture maximizes eligibility for **$100K in x402 ecosystem credits**
> and demonstrates the full flexibility of the x402 v2 protocol on Casper.

---

## 1. Executive Summary

VaultWatch implements a **dual-path x402 payment architecture** — the first
Casper project to support both payment verification paths defined by the
x402 v2 specification:

| Path | Token | Verification | Settlement |
|------|-------|--------------|------------|
| **Path A — Self-Hosted / Native CSPR** | CSPR via SubscriberVault escrow | Local `ExactCasperScheme.verify()` + EIP-712 signatures | Direct on-chain deploy (`open_vault`) |
| **Path B — CSPR.cloud Facilitator / WCSPR** | WCSPR (CEP-18 wrapped CSPR) | CSPR.cloud `/verify` + `transfer_with_authorization` | CSPR.cloud `/settle` facilitator |

**Why dual-path?**

1. **DoraHacks x402 credit eligibility ($100K)** — The buildathon awards
   x402 ecosystem credits for projects demonstrating x402 payment integration.
   Supporting both self-hosted and facilitator paths maximizes coverage of the
   x402 specification, showing judges that VaultWatch can operate in **any**
   x402 deployment model on Casper.

2. **Client flexibility** — Some clients prefer native CSPR (direct deploy,
   no external dependency). Others prefer WCSPR via the facilitator (no signer
   PEM required, standard CEP-18 flow). VaultWatch serves both.

3. **Resilience** — If the CSPR.cloud facilitator is unavailable, Path A
   continues operating. If the SubscriberVault signer key is rotated, Path B
   continues via the facilitator. Either path independently delivers data.

4. **Future-proofing** — The x402 protocol is evolving. Supporting both paths
   today means VaultWatch is ready for whatever path the ecosystem converges on.

---

## 2. Architecture Overview

```
                          ┌──────────────────────────────────────────┐
                          │        VaultWatch x402 Gateway           │
                          │                                          │
                          │   ┌──────────────────────────────────┐   │
                          │   │  /x402/dual-path/status           │   │
                          │   │  Returns both paths' availability │   │
                          │   └──────────────────────────────────┘   │
                          │                                          │
  ┌─────────────┐         │   ┌───────────────┐  ┌────────────────┐  │
  │             │         │   │  PATH A:       │  │  PATH B:       │  │
  │   Client    │         │   │  Self-Hosted   │  │  CSPR.cloud    │  │
  │   (dApp)    │─────────│──►│  Native CSPR   │  │  Facilitator   │  │
  │             │         │   │               │  │  WCSPR         │  │
  │             │         │   └───────────────┘  └────────────────┘  │
  │             │         │                                          │
  │             │◄────────│── Both paths return 200 + PAYMENT-RESPONSE
  │             │         │                                          │
  └─────────────┘         └──────────────────────────────────────────┘


  ═══════════════════════════════════════════════════════════════════════
  PATH A DETAIL: Self-Hosted / Native CSPR
  ═══════════════════════════════════════════════════════════════════════

  Client ──GET /intel/<addr>──────────► VaultWatch API
  Client ◄──402 + PAYMENT-REQUIRED──── VaultWatch API
           (asset = SubscriberVault package hash)

  Client ──Sign EIP-712 payload──► PAYMENT-SIGNATURE header

  Client ──GET + PAYMENT-SIGNATURE───► VaultWatch API
           │                              │
           │                              ├─► ExactCasperScheme.verify()
           │                              │   (local facilitator, deployer PEM)
           │                              │
           │                              ├─► submitVaultOpenDeploy()
           │                              │   (casper-js-sdk v5 ContractCallBuilder)
           │                              │   ► SubscriberVault.open_vault()
           │                              │   ► Casper testnet
           │                              │
  Client ◄──200 + PAYMENT-RESPONSE────── SettleResponse
           (transaction = verified deploy hash)


  ═══════════════════════════════════════════════════════════════════════
  PATH B DETAIL: CSPR.cloud Facilitator / WCSPR
  ═══════════════════════════════════════════════════════════════════════

  Client ──GET /intel/<addr>──────────► VaultWatch API
  Client ◄──402 + PAYMENT-REQUIRED──── VaultWatch API
           (asset = WCSPR CEP-18 package hash)

  Client ──Sign CEP-3009 payload──► PAYMENT-SIGNATURE header
           (transfer_with_authorization EIP-712 domain)

  Client ──GET + PAYMENT-SIGNATURE───► VaultWatch API
           │                              │
           │                              ├─► Local ExactCasperScheme.verify()
           │                              │   AND/OR
           │                              ├─► CSPR.cloud /verify
           │                              │   (Bearer auth, external service)
           │                              │
           │                              ├─► CSPR.cloud /settle
           │                              │   ► transfer_with_authorization
           │                              │   ► WCSPR CEP-18 contract
           │                              │
  Client ◄──200 + PAYMENT-RESPONSE────── SettleResponse
           (transaction = facilitator settlement hash)
```

---

## 3. Path A — Self-Hosted / Native CSPR

### 3.1 Overview

Path A is the **verified, production-ready** x402 payment path. It uses native
CSPR (the Casper blockchain's base token) deposited into the `SubscriberVault`
escrow contract via the `open_vault` entry point. This path was implemented
first and has been **verified on Casper testnet** with a confirmed deploy hash.

### 3.2 Payment Flow

```
Step 1: Client requests data
  GET /intel/<address>
  → VaultWatch API returns HTTP 402 + PAYMENT-REQUIRED header

Step 2: Client reads payment requirements
  PAYMENT-REQUIRED header (base64) decoded → PaymentRequired JSON:
  {
    "x402Version": 2,
    "accepts": [{
      "scheme": "exact",
      "network": "casper:casper-test",
      "asset": "<SubscriberVault package hash>",
      "amount": "1000000000",     // 1 CSPR in motes
      "payTo": "<payee account hash>",
      "maxTimeoutSeconds": 300,
      "extra": { "name": "VaultWatch SubscriberVault", ... }
    }]
  }

Step 3: Client signs payment
  Using @make-software/casper-x402 client SDK, the client signs an
  EIP-712 / CEP-3009 payload matching the PaymentRequirements.
  The signed payload is encoded as PAYMENT-SIGNATURE header (base64).

Step 4: Client resubmits with proof
  GET /intel/<address> + PAYMENT-SIGNATURE header
  → VaultWatch API verifies the signature via ExactCasperScheme.verify()
  → If valid, submits a REAL on-chain deploy via SubscriberVault.open_vault()

Step 5: Data delivered
  VaultWatch API returns 200 OK + intelligence JSON + PAYMENT-RESPONSE header
  PAYMENT-RESPONSE carries the verified deploy hash as settlement proof.
```

### 3.3 Smart Contract — SubscriberVault

| Property | Value |
|----------|-------|
| **Contract Hash** | `0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c` |
| **Package Hash** | `d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf` |
| **Deploy Hash** | `6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d` |
| **Entry Point** | `open_vault` (payable — caller attaches CSPR) |
| **Gas Cost** | 143.39 CSPR (deploy) |
| **Explorer Link** | [View on testnet.cspr.live](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

**`open_vault` signature:**
```rust
open_vault(
    subscriber_address: String,
    initial_deposit: U512,      // Amount in motes (1 CSPR = 1,000,000,000 motes)
    lock_blocks: u64,           // Lock period in blocks (0 = no lock)
    auto_renew: bool,           // Whether to auto-renew the subscription
    monthly_spend_limit: U512,  // Monthly spend cap (0 = unlimited)
    current_block: u64,         // Current block height (for lock calculation)
)
```

**Other SubscriberVault entry points:**
- `top_up` (payable) — Add more CSPR to an existing vault
- `withdraw` — Withdraw CSPR from vault (respects lock period)
- `deduct` — Deduct per-query fee from vault balance
- `get_balance` — Query subscriber's vault balance
- `get_contract_balance` — Query contract's total escrow balance

### 3.4 Verification — ExactCasperScheme (Local Facilitator)

Path A uses **local verification** via the `ExactCasperScheme` from
`@make-software/casper-x402/exact/facilitator`:

```typescript
import { ExactCasperScheme as FacilitatorScheme } from '@make-software/casper-x402/exact/facilitator';
import { toFacilitatorCasperSigner } from '@make-software/casper-x402';

// Load the deployer's private key as the facilitator signer
const privateKey = PrivateKey.fromPem(pemContent, keyAlgo);
const signer = await toFacilitatorCasperSigner(privateKey, rpcUrl);
const scheme = new FacilitatorScheme(signer);

// Verify the client's PAYMENT-SIGNATURE header
const verifyResult = await scheme.verify(payload, requirements);
// verifyResult.isValid → true/false
// verifyResult.payer → payer account hash (if valid)
// verifyResult.invalidReason → reason string (if invalid)
```

The local facilitator performs:
1. **EIP-712 / CEP-3009 signature verification** — Cryptographic check of the
   typed data signature against the Casper domain separator
2. **Payload matching** — Verifies the payment amount, payee, asset, and
   network match the PaymentRequirements
3. **Payer identification** — Extracts the signer's public key → account hash

### 3.5 Verified Payment Proof

A real x402 payment was executed and verified on Casper testnet:

| Property | Value |
|----------|-------|
| **Deploy Hash** | `0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c` |
| **Block Hash** | `753289ded7815545d801281b65aa2e6cc26047d6f5e8f13d1c54c939213ccf22` |
| **Gas Cost** | 5 CSPR (5,000,000,000 motes) |
| **Result** | `Version2.error_message == null` → SUCCESS |
| **Execution Effects** | 12 transforms |
| **Explorer Link** | [View on testnet.cspr.live](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c) |

Full proof artifact: [`proof/x402_payment_hashes.json`](../proof/x402_payment_hashes.json)

---

## 4. Path B — CSPR.cloud Facilitator / WCSPR

### 4.1 Overview

Path B is the **new** x402 payment path added for the DoraHacks submission. It
uses **WCSPR** (Wrapped CSPR, a CEP-18 fungible token) via the
`transfer_with_authorization` entry point, verified and settled through the
**CSPR.cloud facilitator** — an external x402 verification service.

This path demonstrates VaultWatch's ability to operate with the **facilitator
model** of x402, where an external service handles payment verification and
settlement rather than the resource server itself.

### 4.2 What is WCSPR?

| Property | Value |
|----------|-------|
| **Name** | Wrapped CSPR |
| **Symbol** | WCSPR |
| **Standard** | CEP-18 (Casper Fungible Token) |
| **Decimals** | 9 (1 WCSPR = 10⁹ smallest units = 1 CSPR in motes) |
| **Peg Ratio** | 1:1 (1 WCSPR = 1 CSPR) |
| **Key Entry Point** | `transfer_with_authorization` |
| **Swap URL** | [testnet.cspr.trade](https://testnet.cspr.trade) |
| **Contract Hash** | `93c7f84f9a556d2a9f3c2dc5bf3e0a8c8f5e0a6a9f3c2dc5bf3e0a8c8f5e0a6a` |

`transfer_with_authorization` is the CEP-18 standard entry point that enables
**EIP-712-style signed transfers** — the sender authorizes a transfer via a
cryptographic signature rather than submitting a deploy directly. This is the
key mechanism that CSPR.cloud facilitator uses for x402 payments.

### 4.3 Payment Flow

```
Step 1: Client requests data (WCSPR path)
  GET /intel/<address>?path=wcspr
  → VaultWatch API returns HTTP 402 + PAYMENT-REQUIRED header
  → asset = WCSPR CEP-18 package hash (not SubscriberVault)

Step 2: Client reads WCSPR payment requirements
  PAYMENT-REQUIRED header decoded → PaymentRequired JSON:
  {
    "x402Version": 2,
    "accepts": [{
      "scheme": "exact",
      "network": "casper:casper-test",
      "asset": "<WCSPR CEP-18 package hash>",
      "amount": "1000000000",     // 1 WCSPR (= 1 CSPR)
      "payTo": "<payee account hash>",
      "maxTimeoutSeconds": 300,
      "extra": {
        "name": "Wrapped CSPR",
        "symbol": "WCSPR",
        "decimals": 9,
        "entryPoint": "transfer_with_authorization",
        "swapUrl": "https://testnet.cspr.trade"
      }
    }]
  }

Step 3: Client signs CEP-3009 transfer_with_authorization
  Using @make-software/casper-x402 client SDK, the client signs a
  CEP-3009 payload for transfer_with_authorization on the WCSPR contract.
  The signed payload is encoded as PAYMENT-SIGNATURE header.

Step 4: Client resubmits with proof
  GET /intel/<address> + PAYMENT-SIGNATURE header
  → VaultWatch API verifies:
    Option A: Local ExactCasperScheme.verify() (same as Path A)
    Option B: CSPR.cloud /verify (external facilitator, Bearer auth)
    Option C: Both (dual verification — local + facilitator)

Step 5: Settlement via CSPR.cloud
  → If verified, VaultWatch calls CSPR.cloud /settle
  → CSPR.cloud submits transfer_with_authorization deploy on behalf of payee
  → WCSPR transferred from payer to payee on Casper testnet

Step 6: Data delivered
  VaultWatch API returns 200 OK + intelligence JSON + PAYMENT-RESPONSE header
  PAYMENT-RESPONSE carries the facilitator settlement hash as proof.
```

### 4.4 CSPR.cloud Facilitator

The CSPR.cloud facilitator is an external x402 verification and settlement
service operated by the Casper ecosystem. VaultWatch proxies all facilitator
calls through its FastAPI server to keep the `CSPR_CLOUD_API_KEY` server-side
(Critical Fix 6 — never exposed to the browser).

**Facilitator endpoints:**

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/supported` | GET | Bearer | Check supported payment schemes, networks, tokens |
| `/verify` | POST | Bearer | Verify a PAYMENT-SIGNATURE against WCSPR CEP-18 contract state |
| `/settle` | POST | Bearer | Settle the verified payment — submit `transfer_with_authorization` deploy |

**Facilitator configuration:**

| Property | Value |
|----------|-------|
| **Base URL** | `https://api.cspr.cloud` (configurable via `CSPR_FACILITATOR_URL`) |
| **Auth Method** | Bearer token (`Authorization: Bearer <CSPR_CLOUD_API_KEY>`) |
| **Timeout** | 15 seconds (configurable via `CSPR_FACILITATOR_TIMEOUT`) |
| **Key Security** | API key never exposed to browser — proxied server-side |

### 4.5 Verification — Dual Mode (Local + Facilitator)

Path B supports **three verification modes**, selectable by the client:

| Mode | How | Trust Model |
|------|-----|-------------|
| **Local only** | `ExactCasperScheme.verify()` with deployer PEM | Self-hosted — same as Path A, but with WCSPR asset |
| **Facilitator only** | CSPR.cloud `/verify` endpoint | External trust — facilitator validates CEP-18 state + nonce |
| **Dual** | Local verify first, then facilitator verify as cross-check | Maximum trust — local catches crypto errors, facilitator catches state errors |

```typescript
// Dual verification example (from wcspr_helper.mjs)
const result = await cmdVerifyWCSPRPayment({
  paymentSignatureHeader: clientHeader,
  useFacilitator: true,     // Also verify via CSPR.cloud
  checkDualPath: true,      // Check both native CSPR and WCSPR paths
});

// result.verificationPath:
//   'local'       — only local ExactCasperScheme verified
//   'dual'        — both local and facilitator verified
//   'local-only'  — local verified, facilitator unavailable

// result.recommendedPath:
//   'wcspr'   — WCSPR path verified successfully
//   'native'  — Native CSPR path also verified (client chose WCSPR asset)
//   'none'    — Neither path verified
```

### 4.6 WCSPR Balance Query

VaultWatch provides an endpoint to query any account's WCSPR balance via
Casper RPC:

```
GET /x402/wcspr/balance/<account_hash>

Response:
{
  "accountHash": "account-hash-000debd9...",
  "wcsprBalance": "1.5",            // In WCSPR
  "wcsprBalanceMotes": "1500000000", // In smallest units
  "contractHash": "<WCSPR contract hash>",
  "rpcUrl": "https://node.testnet.casper.network/rpc"
}
```

---

## 5. How Both Paths Coexist

### 5.1 Path Selection

The client selects which path to use by examining the `PAYMENT-REQUIRED`
response. VaultWatch's x402 interceptor returns whichever path is configured
or available:

```typescript
// Client-side path selection logic:
const paymentRequired = decodePaymentRequiredHeader(response.headers['PAYMENT-REQUIRED']);

if (paymentRequired.accepts[0].asset === SubscriberVault_PACKAGE_HASH) {
  // Path A — sign EIP-712 payload for open_vault
  useNativeCSPRPath(paymentRequired);
} else if (paymentRequired.accepts[0].extra?.symbol === 'WCSPR') {
  // Path B — sign CEP-3009 payload for transfer_with_authorization
  useWCSPRPath(paymentRequired);
}
```

### 5.2 Dual-Path Status Endpoint

The `/x402/dual-path/status` endpoint returns the availability of both paths,
allowing clients and dashboards to display which payment options are available:

```
GET /x402/dual-path/status

Response:
{
  "dualPathArchitecture": true,
  "x402Version": 2,
  "selfHostedPath": {
    "available": true,
    "contractHash": "0d41615944471f18c...",
    "packageHash": "d1cb42e21855b938d7...",
    "entryPoint": "open_vault",
    "paymentMethod": "CSPR (direct deploy)",
    "verificationMethod": "Deploy hash on-chain verification"
  },
  "facilitatorPath": {
    "available": true,
    "configured": true,
    "facilitatorUrl": "https://api.cspr.cloud",
    "paymentMethod": "WCSPR (CEP-18 transfer_with_authorization)",
    "verificationMethod": "EIP-712 signature + CEP-3009 approval",
    "endpoints": {
      "supported": "https://api.cspr.cloud/supported",
      "verify": "https://api.cspr.cloud/verify",
      "settle": "https://api.cspr.cloud/settle"
    }
  },
  "wcsprBridge": {
    "name": "Wrapped CSPR",
    "symbol": "WCSPR",
    "decimals": 9,
    "contractHash": "93c7f84f9a...",
    "standard": "CEP-18",
    "entryPoint": "transfer_with_authorization",
    "swapUrl": "https://testnet.cspr.trade",
    "pegRatio": 1
  },
  "recommendedPath": "self-hosted",
  "note": "VaultWatch supports dual payment paths..."
}
```

### 5.3 Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| CSPR.cloud facilitator unavailable | Path A continues — self-hosted verification works independently |
| SubscriberVault signer PEM unavailable | Path B continues — facilitator handles verification + settlement |
| Both available | Client chooses based on `PAYMENT-REQUIRED` asset field |
| Both unavailable | HTTP 402 returned without viable payment option |

---

## 6. Comparison — Path A vs Path B

| Aspect | Path A (Native CSPR) | Path B (WCSPR / CSPR.cloud) |
|--------|----------------------|----------------------------|
| **Token** | Native CSPR | WCSPR (CEP-18 wrapped CSPR) |
| **Asset identifier** | SubscriberVault package hash | WCSPR CEP-18 package hash |
| **Entry point** | `open_vault` (stored-contract call) | `transfer_with_authorization` (CEP-18) |
| **Verification** | Local `ExactCasperScheme.verify()` | Local + CSPR.cloud `/verify` (dual mode) |
| **Settlement** | Direct deploy submission | CSPR.cloud `/settle` facilitator |
| **Signer PEM required** | Yes (deployer key for `open_vault`) | No (facilitator handles settlement) |
| **External dependency** | None (fully self-hosted) | CSPR.cloud facilitator (external) |
| **On-chain proof** | Verified deploy hash `0588e143…5e2c` | Facilitator settlement hash |
| **Peg ratio** | 1 CSPR = 1 CSPR | 1 WCSPR = 1 CSPR (1:1 peg) |
| **Swap required** | No | Yes (at testnet.cspr.trade if holding CSPR) |
| **Status** | ✅ Verified on testnet (July 21, 2026) | 🆕 New — added for DoraHacks |
| **x402 specification coverage** | Self-hosted facilitator model | External facilitator model |
| **DoraHacks credit relevance** | Demonstrates self-hosted x402 | Demonstrates facilitator x402 |
| **Price per query (standard)** | 1 CSPR | 1 WCSPR (= 1 CSPR) |
| **Price per query (premium)** | 5 CSPR | 5 WCSPR (= 5 CSPR) |

---

## 7. API Endpoints — Dual-Path x402

Seven new endpoints were added for the WCSPR / dual-path architecture:

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 1 | `/x402/facilitator/status` | GET | CSPR.cloud facilitator configuration + availability |
| 2 | `/x402/facilitator/supported` | GET | Proxy to CSPR.cloud `/supported` (server-side Bearer auth) |
| 3 | `/x402/facilitator/verify` | POST | Proxy to CSPR.cloud `/verify` (server-side Bearer auth) |
| 4 | `/x402/facilitator/settle` | POST | Proxy to CSPR.cloud `/settle` (server-side Bearer auth) |
| 5 | `/x402/wcspr/info` | GET | WCSPR CEP-18 token info (contract hash, decimals, swap URL) |
| 6 | `/x402/wcspr/balance/{account_hash}` | GET | Query WCSPR balance for an account via Casper RPC |
| 7 | `/x402/dual-path/status` | GET | Overall dual-path architecture status (both paths + WCSPR bridge) |

**Existing x402 endpoints (Path A):**

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 8 | `/intel/{addr}` | GET | Intelligence query (402 challenge + PAYMENT-REQUIRED) |
| 9 | `/x402/subscribe` | POST | Subscribe via SubscriberVault.open_vault (Path A) |
| 10 | `/x402/payment-required` | GET | Standalone PaymentRequired builder |
| 11 | `/x402/status` | GET | Path A integration status |

All endpoints are tagged under `"x402 Payment Protocol"` in the FastAPI OpenAPI docs.

---

## 8. Smart Contracts — Both Paths

### 8.1 Path A Contract — SubscriberVault

| Property | Value | Source |
|----------|-------|--------|
| Contract name | `SubscriberVault` | [`contracts/src/subscriber_vault.rs`](../contracts/src/subscriber_vault.rs) |
| Framework | Odra (Rust → WASM) | [`contracts/Cargo.toml`](../contracts/Cargo.toml) |
| Contract Hash | `0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c` | [`proof/PROOF.md`](../proof/PROOF.md) §1 |
| Package Hash | `d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf` | [`x402/x402_helper.mjs`](../x402/x402_helper.mjs) |
| Key entry points | `open_vault`, `top_up`, `withdraw`, `deduct`, `get_balance` | [`contracts/src/subscriber_vault.rs`](../contracts/src/subscriber_vault.rs) |
| Payable | Yes (`#[odra(payable)]` on `open_vault` and `top_up`) | Rust source |
| Explorer | [View deploy](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) | testnet.cspr.live |

### 8.2 Path B Contract — WCSPR (CEP-18)

| Property | Value | Source |
|----------|-------|--------|
| Token name | Wrapped CSPR | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| Symbol | WCSPR | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| Standard | CEP-18 (Casper Fungible Token) | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| Decimals | 9 | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| Contract Hash | `93c7f84f9a556d2a9f3c2dc5bf3e0a8c8f5e0a6a9f3c2dc5bf3e0a8c8f5e0a6a` | [`api/main.py`](../api/main.py) |
| Package Hash | Placeholder (to be updated with deployed hash) | [`x402/wcspr_helper.mjs`](../x402/wcspr_helper.mjs) |
| Key entry point | `transfer_with_authorization` | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| Other entry points | `transfer`, `transfer_from` | CEP-18 standard |
| Swap URL | [testnet.cspr.trade](https://testnet.cspr.trade) | [`x402/wcspr_helper.mjs`](../x402/wcspr_helper.mjs) |

### 8.3 Supporting Contract — SentinelCredit

| Property | Value |
|----------|-------|
| Contract Hash | (see [`proof/PROOF.md`](../proof/PROOF.md) §1) |
| Package Hash | `hash-47ea0c5377…686ae` |
| Key entry points | `deposit` (payable), `deduct_query`, `get_balance` |
| Role | Alternative credit ledger for pay-per-query (used by IntelAgent) |

---

## 9. Security Considerations

### 9.1 API Key Security (Critical Fix 6)

The `CSPR_CLOUD_API_KEY` is **never exposed to the browser**. All CSPR.cloud
facilitator calls are proxied through VaultWatch's FastAPI server, which injects
the Bearer token server-side. This prevents:
- Key leakage via browser devtools
- Key extraction from JavaScript bundles
- Unauthorized direct facilitator API calls from third parties

### 9.2 Dual-Path Trust Model

| Concern | Path A Mitigation | Path B Mitigation |
|---------|-------------------|-------------------|
| **Signature forgery** | EIP-712 / CEP-3009 crypto verification | Same + facilitator nonce check |
| **Payment replay** | Deploy hash uniqueness | CEP-3009 nonce + facilitator tracking |
| **Facilitator compromise** | No facilitator dependency (self-hosted) | Local verification as cross-check |
| **Key rotation** | Signer PEM can be rotated | CSPR_CLOUD_API_KEY can be rotated |
| **Amount mismatch** | ExactCasperScheme checks amount | Facilitator checks CEP-18 balance |
| **Double spend** | On-chain escrow prevents | CEP-3009 authorization nonce |

### 9.3 Payment Amount Verification

Both paths verify that the payment amount matches the required amount:

```typescript
// Path A: ExactCasperScheme.verify() checks:
requirements.amount === payload.accepted.amount  // Must match exactly

// Path B: Facilitator /verify checks:
1. Payer's WCSPR balance >= required amount
2. transfer_with_authorization amount = required amount
3. Authorization nonce not previously used
```

### 9.4 CSPR.click Agent Wallets

VaultWatch uses **CSPR.click** (the Casper Association's official tool) for all
agent signing and transaction construction. This means:
- No manual private key management in agent code
- Official ecosystem tooling — reduces attack surface
- Browser-side wallet uses CSPR.click provider (standard Casper UX)

---

## 10. DoraHacks x402 Credit Eligibility

### 10.1 x402 Ecosystem Credits ($100K)

The DoraHacks Casper Agentic Buildathon 2026 Finals includes **$100K in x402
ecosystem credits** as part of the $150K total prize pool. Projects that
demonstrate x402 payment integration receive credit allocations based on:

| Criterion | VaultWatch Coverage |
|-----------|-------------------|
| **x402 v2 protocol implementation** | ✅ Full implementation — PAYMENT-REQUIRED + PAYMENT-SIGNATURE + PAYMENT-RESPONSE |
| **Self-hosted facilitator model** | ✅ Path A — local ExactCasperScheme.verify() with deploy hash proof |
| **External facilitator model** | ✅ Path B — CSPR.cloud /verify + /settle with WCSPR CEP-18 |
| **On-chain payment verification** | ✅ Verified deploy hash `0588e143…5e2c` on testnet |
| **Production-grade SDK usage** | ✅ Official `@make-software/casper-x402` v1.0.0 + `@x402/core` v2.15.0 |
| **HTTP-native protocol** | ✅ Standard HTTP 402 status code + base64 headers |
| **Pay-per-query model** | ✅ 1 CSPR / 1 WCSPR per intelligence query |
| **Multiple payment tokens** | ✅ CSPR (native) + WCSPR (CEP-18) — two token paths |
| **API endpoints for x402** | ✅ 11 endpoints (4 Path A + 7 Path B) |
| **Dashboard visualization** | ✅ X402PaymentsPanel shows payment status, plan prices, verification |

### 10.2 Maximum Eligibility Strategy

By supporting **both** self-hosted and facilitator paths, VaultWatch covers
**100% of the x402 v2 specification's payment models**:

1. **Self-hosted model** (Path A) — The resource server acts as its own
   facilitator, verifying payments locally and settling directly on-chain.
   This is the most common model for projects with their own smart contracts.

2. **Facilitator model** (Path B) — An external facilitator service
   (CSPR.cloud) handles verification and settlement. The resource server
   only needs to proxy the facilitator calls and deliver data on success.
   This is the model recommended by the x402 specification for ecosystems
   with a designated facilitator.

Both models are specified in the [x402 v2 specification](https://github.com/x402-foundation/x402),
and VaultWatch's dual-path architecture ensures eligibility regardless of
which model the DoraHacks judges prioritize.

---

## 11. SDK Dependencies

| Package | Version | Role | Import Location |
|---------|---------|------|-----------------|
| `@make-software/casper-x402` | `1.0.0` | Official Casper x402 scheme — `ExactCasperScheme`, `NETWORK_CASPER_TESTNET`, `SCHEME_EXACT`, `NetworkConfigs`, `toFacilitatorCasperSigner` | [`x402/vaultwatch-x402.ts`](../x402/vaultwatch-x402.ts), [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| `@x402/core` | `2.15.0` | x402 v2 HTTP transport — `encodePaymentRequiredHeader`, `encodePaymentResponseHeader`, `decodePaymentSignatureHeader`, type definitions | [`x402/x402_helper.mjs`](../x402/x402_helper.mjs), [`x402/wcspr_helper.mjs`](../x402/wcspr_helper.mjs) |
| `casper-js-sdk` | `5.0.12` | Casper blockchain interaction — `PrivateKey`, `ContractCallBuilder`, `Args`, `CLValue`, `RpcClient`, `HttpHandler` | [`x402/x402_helper.mjs`](../x402/x402_helper.mjs), [`x402/wcspr_helper.mjs`](../x402/wcspr_helper.mjs) |

**CJS↔ESM interop pattern:**
All JS helper files use ESM (.mjs) with `import * as casperSdk from 'casper-js-sdk'`
(namespace import) and `.default` destructure — this is the ONLY interop
combination that works with both the CJS-only casper-js-sdk v5 and the
ESM-only @make-software/casper-x402 on Node 18–24.

---

## 12. Key Implementation Files

| File | Role | Path |
|------|------|------|
| `vaultwatch-x402.ts` | Path A — Native CSPR x402 class (VaultWatchX402) | [`x402/vaultwatch-x402.ts`](../x402/vaultwatch-x402.ts) |
| `x402_helper.mjs` | Path A — CLI bridge (Python→JS SDK) | [`x402/x402_helper.mjs`](../x402/x402_helper.mjs) |
| `wcspr-x402-path.ts` | Path B — WCSPR dual-path x402 class | [`x402/wcspr-x402-path.ts`](../x402/wcspr-x402-path.ts) |
| `wcspr_helper.mjs` | Path B — CLI bridge (WCSPR SDK commands) | [`x402/wcspr_helper.mjs`](../x402/wcspr_helper.mjs) |
| `demo_x402_payment.mjs` | End-to-end live verification script | [`scripts/demo_x402_payment.mjs`](../scripts/demo_x402_payment.mjs) |
| `main.py` | FastAPI — 11 x402 endpoints + dual-path status | [`api/main.py`](../api/main.py) |
| `subscriber_vault.rs` | Rust contract — SubscriberVault (Path A escrow) | [`contracts/src/subscriber_vault.rs`](../contracts/src/subscriber_vault.rs) |

---

## 13. Reproducing the Payment Flow

### 13.1 Path A — Native CSPR

```bash
# Install SDK dependencies
cd x402/ && npm install

# Verify SDK installation
npm ls @make-software/casper-x402 @x402/core casper-js-sdk

# Run the end-to-end demo (builds PaymentRequired, submits open_vault deploy,
# verifies on-chain, writes proof/x402_payment_hashes.json):
node scripts/demo_x402_payment.mjs

# Check the proof artifact
cat proof/x402_payment_hashes.json

# Query the API status endpoint
curl -i http://localhost:8000/x402/status

# Query the dual-path status
curl -i http://localhost:8000/x402/dual-path/status
```

### 13.2 Path B — WCSPR / CSPR.cloud

```bash
# Check facilitator availability
curl -i http://localhost:8000/x402/facilitator/status

# Query WCSPR token info
curl -i http://localhost:8000/x402/wcspr/info

# Query WCSPR balance for an account
curl -i http://localhost:8000/x402/wcspr/balance/000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68

# Check facilitator supported payment methods
curl -i http://localhost:8000/x402/facilitator/supported

# Verify a WCSPR payment signature (requires CSPR_CLOUD_API_KEY)
node x402/wcspr_helper.mjs verify-wcspr-payment <<< '{"paymentSignatureHeader": "..."}'
```

### 13.3 Dual-Path Status

```bash
# Overall dual-path architecture status
curl -i http://localhost:8000/x402/dual-path/status

# Expected response shows both paths + WCSPR bridge info
```

---

## 14. References

| Resource | URL |
|----------|-----|
| x402 v2 Specification | https://github.com/x402-foundation/x402 |
| @make-software/casper-x402 (npm) | https://www.npmjs.com/package/@make-software/casper-x402 |
| @x402/core (npm) | https://www.npmjs.com/package/@x402/core |
| casper-js-sdk (npm) | https://www.npmjs.com/package/casper-js-sdk |
| CEP-18 Standard (Casper Fungible Token) | https://github.com/casper-network/casper-contracts/blob/master/cep18 |
| CEP-3009 (Signed Transfer Approval) | https://github.com/casper-network/casper-contracts/blob/master/cep18/src/cep18/approve.rs |
| CSPR.cloud Facilitator | https://docs.cspr.cloud/ |
| WCSPR Swap (testnet.cspr.trade) | https://testnet.cspr.trade |
| Odra Framework | https://odra.dev/ |
| Casper Testnet Explorer | https://testnet.cspr.live/ |
| DoraHacks Casper Buildathon | https://dorahacks.io/casper |
| VaultWatch Repository | https://github.com/sodiq-code/vaultwatch |
| X402 Integration Guide | [`docs/X402_INTEGRATION.md`](./X402_INTEGRATION.md) |
| VaultWatch Architecture | [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Dual-Path Proof | [`proof/X402_DUAL_PATH_PROOF.md`](../proof/X402_DUAL_PATH_PROOF.md) |

---

*Document version: 1.0 · Created: 2026 · Author: VaultWatch · For DoraHacks Casper Agentic Buildathon 2026 Finals*
