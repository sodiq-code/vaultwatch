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
┌──────────┐   1. GET /intel/<address>        ┌──────────────┐
│  Client  │ ───────────────────────────────► │ VaultWatch   │
│ (dApp)   │                                  │ API          │
│          │ ◄─────────────────────────────── │              │
│          │   2. HTTP 402 + x402 payment     │              │
│          │      requirements                │              │
│          │                                  │              │
│          │   3. Sign payment to             │              │
│          │      SubscriberVault             │              │
│          │      via @make-software/         │              │
│          │      casper-x402 SDK             │              │
│          │                                  │              │
│          │   4. POST payment proof          │              │
│          │ ───────────────────────────────► │              │
│          │                                  │ 5. Verify    │
│          │                                  │    on-chain  │
│          │                                  │    via SDK   │
│          │ ◄─────────────────────────────── │              │
│          │   6. 200 OK + intelligence JSON  │              │
└──────────┘                                  └──────────────┘
```

## 3. Installation

```bash
# In the x402/ directory
cd x402/
npm install @make-software/casper-x402 casper-js-sdk
```

The `x402/package.json` declares these as `peerDependencies` so they
install alongside the VaultWatch package.

## 4. Usage

### 4.1 Subscribe (open a vault)

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

### 4.2 Query intelligence (paid)

```typescript
// Client-side: receive 402, sign, resubmit
const response = await fetch('https://api.vaultwatch.io/intel/0xabc...');
if (response.status === 402) {
  const paymentRequest = await response.json();
  // Sign payment via @make-software/casper-x402 client SDK
  const proof = await signX402Payment(paymentRequest, myKeyPair);
  // Resubmit with proof
  const finalResponse = await fetch('https://api.vaultwatch.io/intel/0xabc...', {
    headers: { 'X-Payment-Proof': JSON.stringify(proof) },
  });
  const intelligence = await finalResponse.json();
}
```

### 4.3 Verify payment (server-side)

```typescript
const x402 = new VaultWatchX402({ network: 'testnet' });
const verification = await x402.verifyPayment(proof);
if (verification.verified) {
  // Serve the intelligence finding
  serveIntel(address);
  // Record the spend on-chain via SubscriberVault.deduct()
}
```

## 5. Contract Bindings

The official SDK binds to two VaultWatch contracts:

| Contract | Entry point | Called when |
|----------|-------------|-------------|
| `SubscriberVault` | `open_vault()` | Subscribe — escrow initial deposit |
| `SubscriberVault` | `deduct()` | Per-query — deduct from escrow |
| `SentinelCredit` | `deposit()` | Top up credit balance |
| `SentinelCredit` | `deduct_query()` | Per-query — deduct query price |

After deploying contracts via `scripts/deploy_contracts_live.py`, set
the contract hashes as env vars:

```bash
export SUBSCRIBER_VAULT_HASH=<hash-from-deploy_hashes_live.json>
export SENTINEL_CREDIT_HASH=<hash-from-deploy_hashes_live.json>
```

## 6. Real Payment Transaction

Once contracts are deployed, a real x402 payment transaction looks like:

```bash
# 1. Subscribe (escrow 10 CSPR)
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

# 2. Query (deduct 1 CSPR)
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

## 7. Migration Path from Stub

The old `agents/intel_agent.py::serve_intel_with_x402()` is preserved
for backwards compatibility (tests depend on it). The new flow is:

1. **Production**: use `x402/vaultwatch-x402.ts` + official SDK
2. **Testing/mock**: use the old Python stub (set `CASPER_MOCK=true`)
3. **MCP**: the new `x402_subscribe` MCP tool (tool #18) wraps the
   official SDK and returns the real payment request structure

## 8. Verification Checklist

- [ ] `@make-software/casper-x402` appears in `x402/package.json` peerDependencies
- [ ] `VaultWatchX402` class imports the SDK via dynamic `import()`
- [ ] `subscribe()` returns a real `PaymentRequest` from the SDK
- [ ] `verifyPayment()` calls the SDK's verification, not a stub
- [ ] `SUBSCRIBER_VAULT_HASH` and `SENTINEL_CREDIT_HASH` env vars are
      documented and set after deploy
- [ ] At least one real payment deploy hash is recorded in `proof/PROOF.md`
