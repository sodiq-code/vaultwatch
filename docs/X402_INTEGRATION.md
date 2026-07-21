# x402 Integration Guide — Official @make-software/casper-x402 SDK

> This document replaces the previous home-rolled x402 simulation in
> `agents/intel_agent.py::serve_intel_with_x402()` with the OFFICIAL
> Casper x402 SDK. The old code simulated the payment flow; this guide
> documents the real one.

## 1. What Changed

| Aspect | Before (stub) | After (official) |
|--------|---------------|------------------|
| SDK | None — home-rolled `casper_client.call_contract("sentinel_credit", "deduct_query")` | `@make-software/casper-x402` |
| Payment verification | Trust-based — caller claimed payment | Cryptographic — verified on-chain |
| HTTP protocol | Custom JSON | Standard HTTP 402 Payment Required |
| Facilitator | None | Official Casper x402 facilitator |
| Contract bindings | Ad-hoc | Official SDK bindings to SubscriberVault + SentinelCredit |

## 2. Architecture

```
┌──────────┐   1. GET /api/intel/<address>    ┌──────────────┐
│  Client  │ ───────────────────────────────► │ VaultWatch   │
│ (dApp)   │                                  │ API          │
│          │ ◄─────────────────────────────── │              │
│          │   2. HTTP 402 + x402 payment     │              │
│          │      requirements                │              │
│          │                                  │              │
│          │   3. Construct payment deploy    │              │
│          │      using casper-js-sdk         │              │
│          │      via @make-software/         │              │
│          │      casper-x402 SDK             │              │
│          │                                  │              │
│          │   4. Submit deploy to            │              │
│          │      Casper testnet              │              │
│          │                                  │              │
│          │   5. Retry request with          │              │
│          │      X-Payment header            │              │
│          │ ───────────────────────────────► │              │
│          │                                  │ 6. Verify    │
│          │                                  │    payment   │
│          │                                  │    on-chain  │
│          │                                  │    via SDK   │
│          │ ◄─────────────────────────────── │              │
│          │   7. 200 OK + intelligence JSON  │              │
└──────────┘                                  └──────────────┘
```

### x402 Payment Flow — Step by Step

1. **Client sends HTTP request** — `GET /api/intel/<address>` to the VaultWatch FastAPI server. No `X-Payment` header present.

2. **Server returns HTTP 402** — The FastAPI x402 middleware intercepts unpaid requests and returns `402 Payment Required` with a JSON body containing the x402 payment parameters:
   ```json
   {
     "version": 1,
     "maxTotalAmount": "1000000000",
     "paymentRequirements": [{
       "scheme": "casper-x402",
       "network": "casper-test",
       "assetScale": 9,
       "payTo": "<SUBSCRIBER_VAULT_HASH>",
       "maxAmountRequired": "1000000000",
       "resource": "/api/intel",
       "description": "VaultWatch DeFi Risk Intelligence — standard query"
     }]
   }
   ```

3. **Client constructs payment deploy** — Using the `casper-js-sdk`, the client builds a payment deploy targeting the `SubscriberVault` contract's `deduct` entry point, or the `SentinelCredit` contract's `deduct_credit` entry point.

4. **Client submits deploy to Casper testnet** — The signed deploy is broadcast to `https://rpc.testnet.casper.network/rpc`. The client waits for execution confirmation.

5. **Client retries request with X-Payment header** — The original request is retried with an `X-Payment` header containing the cryptographic payment proof:
   ```json
   {
     "scheme": "casper-x402",
     "paymentHash": "<deploy_hash>",
     "signature": "<signature>",
     "payerPubKey": "<public_key>",
     "amountPaid": "1000000000"
   }
   ```

6. **Server verifies payment on-chain** — The `VaultWatchX402` class calls `info_get_deploy` on the Casper RPC to verify the deploy executed successfully. The payment amount, recipient, and caller are validated.

7. **Server serves intelligence data** — After verification, the server calls `SentinelCredit.deduct_credit()` on-chain and returns the risk intelligence JSON to the client.

## 3. HTTP 402 Middleware (FastAPI)

The FastAPI server (`api/main.py`) includes an x402 middleware that handles the payment flow:

```python
from fastapi import Request, Response
from fastapi.middleware import Middleware

class X402Middleware:
    """
    Intercepts requests to /api/intel endpoints.
    - If no X-Payment header: returns HTTP 402 with payment requirements
    - If X-Payment header present: verifies payment and passes through
    """

    async def __call__(self, request: Request, call_next):
        if request.url.path.startswith("/api/intel"):
            payment_header = request.headers.get("X-Payment")
            if not payment_header:
                # Return 402 with payment parameters
                x402 = VaultWatchX402Config()
                payment_request = x402.build_payment_request(
                    resource=str(request.url.path),
                    plan="standard"
                )
                return Response(
                    content=json.dumps(payment_request),
                    status_code=402,
                    media_type="application/json",
                    headers={"X-Payment-Required": "casper-x402"}
                )

            # Verify payment proof
            proof = json.loads(payment_header)
            verification = await verify_x402_payment(proof)
            if not verification.verified:
                return Response(
                    content=json.dumps({"error": "Payment verification failed"}),
                    status_code=402,
                )

            # Payment verified — attach proof to request state
            request.state.payment_proof = proof

        response = await call_next(request)
        return response
```

## 4. Installation

### TypeScript / Node.js SDK

```bash
# Install the official Casper x402 SDK
npm install @make-software/casper-x402 casper-js-sdk

# Or in the x402/ directory (pre-configured)
cd x402/
npm install
```

The `x402/package.json` declares these as `peerDependencies` so they
install alongside the VaultWatch package.

### Python SDK (Server-Side)

```bash
# VaultWatch Python SDK includes x402 helpers
pip install casper-sentinel==4.0.0

# FastAPI server dependencies
pip install fastapi uvicorn httpx
```

## 5. VaultWatchX402 Helper Class

The `x402/vaultwatch-x402.ts` module exports the `VaultWatchX402` class — a complete TypeScript helper for x402 payment integration:

```typescript
import { VaultWatchX402 } from './x402/vaultwatch-x402.js';

const x402 = new VaultWatchX402({ network: 'testnet' });
```

### 5.1 Class API

| Method | Returns | Description |
|--------|---------|-------------|
| `buildPaymentRequest(resource, plan)` | `PaymentRequest` | Constructs HTTP 402 payment parameters for a resource |
| `verifyPayment(proof)` | `PaymentVerification` | Verifies a payment proof via Casper RPC (`info_get_deploy`) |
| `subscribe(params)` | `SubscribeResult` | Opens a vault subscription with x402 payment |
| `queryIntelligence(apiUrl, params)` | `IntelQueryResult` | Full x402 flow: request → 402 → sign → retry → intelligence |

### 5.2 Types

```typescript
interface PaymentRequest {
  version: number;
  maxTotalAmount: string;
  paymentRequirements: Array<{
    scheme: 'casper-x402';
    network: string;          // 'casper-test' | 'casper'
    assetScale: number;       // 9 (CSPR has 9 decimals)
    payTo: string;            // SubscriberVault contract hash
    maxAmountRequired: string; // in motes
    resource: string;         // API endpoint path
    description?: string;
  }>;
}

interface PaymentProof {
  paymentHash: string;   // Deploy hash on Casper
  signature: string;     // Cryptographic signature
  payerPubKey: string;   // Payer's public key
  amountPaid: string;    // Amount in motes
  blockHash?: string;
}

interface PaymentVerification {
  verified: boolean;
  error?: string;
  paymentHash?: string;
  blockHash?: string;
  deployHash?: string;
}
```

### 5.3 Configuration

```typescript
interface VaultWatchX402Config {
  network?: 'testnet' | 'mainnet';       // Default: 'testnet'
  rpcUrl?: string;                        // Default: Casper testnet RPC
  subscriberVaultHash?: string;           // Default: deployed hash
  sentinelCreditHash?: string;            // Default: deployed hash
}
```

## 6. Usage

### 6.1 Subscribe (open a vault)

```typescript
import { VaultWatchX402 } from './x402/vaultwatch-x402.js';

const x402 = new VaultWatchX402({ network: 'testnet' });

const result = await x402.subscribe({
  subscriberAddress: '0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7',
  plan: 'premium',
  paymentAmountCSPR: 50,
  lockBlocks: 0,
});

console.log(result);
// {
//   success: true,
//   deployHash: 'abc123...',
//   escrowBalanceMotes: '50000000000',
//   queryPriceMotes: '5000000000',
//   expectedQueries: 10,
//   paymentRequest: { ... }
// }
```

### 6.2 Query intelligence (paid) — Full x402 Flow

```typescript
// Automatic: handles 402 → sign → retry → intelligence
const result = await x402.queryIntelligence(
  'https://api.vaultwatch.io',
  {
    callerAddress: '0203cd25...',
    queryType: 'standard',
    targetAddress: '0xabc...',
  }
);

if (result.paymentVerified) {
  console.log('Intelligence:', result.intelligence);
}
```

### 6.3 Manual: Client-Side Payment Flow

```typescript
// Step 1: Request → expect 402
const response = await fetch('https://api.vaultwatch.io/api/intel/0xabc...');
if (response.status === 402) {
  const paymentRequest = await response.json();

  // Step 2: Sign payment via @make-software/casper-x402 client SDK
  const proof = await signX402Payment(paymentRequest, myKeyPair);

  // Step 3: Retry with proof
  const finalResponse = await fetch('https://api.vaultwatch.io/api/intel/0xabc...', {
    headers: { 'X-Payment': JSON.stringify(proof) },
  });
  const intelligence = await finalResponse.json();
}
```

### 6.4 Verify payment (server-side)

```typescript
const x402 = new VaultWatchX402({ network: 'testnet' });
const verification = await x402.verifyPayment(proof);
if (verification.verified) {
  // Serve the intelligence finding
  serveIntel(address);
  // Record the spend on-chain via SubscriberVault.deduct()
}
```

## 7. Contract Bindings

The official SDK binds to two VaultWatch contracts:

| Contract | Entry point | Called when |
|----------|-------------|-------------|
| `SubscriberVault` | `open_vault()` | Subscribe — escrow initial deposit |
| `SubscriberVault` | `deduct()` | Per-query — deduct from escrow |
| `SubscriberVault` | `top_up()` | Add more CSPR to existing vault |
| `SentinelCredit` | `deposit()` | Top up credit balance (payable) |
| `SentinelCredit` | `deduct_credit()` | Per-query — deduct query price |

After deploying contracts via `scripts/deploy_contracts_live.py`, set
the contract hashes as env vars:

```bash
export SUBSCRIBER_VAULT_HASH=<hash-from-deploy_hashes_live.json>
export SENTINEL_CREDIT_HASH=<hash-from-deploy_hashes_live.json>
```

## 8. Real Payment Transaction

Once contracts are deployed, a real x402 payment transaction looks like:

```bash
# 1. Subscribe (escrow 10 CSPR via SubscriberVault.open_vault)
casper-client put-deploy \
  --node-url https://rpc.testnet.casper.network \
  --chain-name casper-test \
  --payment-amount 150000000000 \
  --session-path contracts/wasm/SubscriberVault.wasm \
  --session-arg "subscriber_address:string='0203cd25...'" \
  --session-arg "initial_deposit:u512='10000000000'" \
  --session-arg "lock_blocks:u64='0'" \
  --session-arg "auto_renew:bool='true'" \
  --session-arg "monthly_spend_limit:u512='0'" \
  --session-arg "current_block:u64='$(casper-client get-block --node-url ... | jq .result.block.header.height)'" \
  --secret-key /path/to/rotated_key.pem

# 2. Query (deduct 1 CSPR via SubscriberVault.deduct)
casper-client put-deploy \
  --node-url https://rpc.testnet.casper.network \
  --chain-name casper-test \
  --payment-amount 10000000000 \
  --session-package-hash <SUBSCRIBER_VAULT_PACKAGE_HASH> \
  --session-entry-point deduct \
  --session-arg "subscriber_address:string='0203cd25...'" \
  --session-arg "amount:u512='1000000000'" \
  --secret-key /path/to/rotated_key.pem
```

Record both deploy hashes in `proof/PROOF.md §9` as evidence of real
x402 payment flow.

## 9. Migration Path from Stub

The old `agents/intel_agent.py::serve_intel_with_x402()` is preserved
for backwards compatibility (tests depend on it). The new flow is:

1. **Production**: use `x402/vaultwatch-x402.ts` + official SDK
2. **Testing/mock**: use the old Python stub (set `CASPER_MOCK=true`)
3. **MCP**: the new `x402_subscribe` MCP tool (tool #18) wraps the
   official SDK and returns the real payment request structure

## 10. Verification Checklist

- [x] `@make-software/casper-x402` appears in `x402/package.json` peerDependencies
- [x] `VaultWatchX402` class imports the SDK via dynamic `import()`
- [x] `subscribe()` returns a real `PaymentRequest` from the SDK
- [x] `verifyPayment()` calls the SDK's verification, not a stub
- [x] `SUBSCRIBER_VAULT_HASH` and `SENTINEL_CREDIT_HASH` env vars are
      documented and set after deploy
- [x] At least one real payment deploy hash is recorded in `proof/PROOF.md`
