# CSPR.click AI Agent Skill — VaultWatch Integration

> **Status:** ✅ Production-ready
> **Task ID:** CSPRCLICK-1
> **Date:** 2026-07-21
> **Skill source:** [make-software/csprclick-examples/csprclick-skill](https://github.com/make-software/csprclick-examples/tree/master/csprclick-skill)

---

## Executive Summary

VaultWatch replaces the prior **manual key management** flow (where a
hardcoded `secret_key.pem` was required at the repo root) with a
**programmatic agent-wallet abstraction** built on the official
**CSPR.click AI Agent Skill** guidance + the canonical Autarca
reference implementation pattern.

The integration spans **both sides** of the Casper wallet ecosystem:

| Layer | Technology | Purpose |
| --- | --- | --- |
| **Server-side (headless)** | `casper-js-sdk` v5 + `PrivateKey.generate()` | Autonomous agent wallet **creation** + **signing** for pytest e2e tests, MCP server deploys, scheduled pipeline writes |
| **Browser-side (user-facing)** | CSPR.click Web SDK (CDN) | End-user wallet connection + transaction approval via Casper Wallet / WalletConnect / social-login wallets |

Both layers use the **same `casper-js-sdk` v5** that CSPR.click uses
under the hood — the CSPR.click AI Agent Skill's own reference
implementation (Autarca) confirms this is the sanctioned pattern for
autonomous agent workflows.

---

## What is the CSPR.click AI Agent Skill?

The CSPR.click AI Agent Skill is an **installable instruction pack**
(`SKILL.md`) published by MAKE Software (the Casper Wallet vendor). It
teaches AI coding assistants (Claude Code, Cursor, Z.ai Code, etc.)
how to correctly integrate the **CSPR.click Web SDK** into dApps.

> "An agent skill is available for the CSPR.click Web SDK. Once
> installed, your AI coding assistant will automatically know how to
> integrate CSPR.click into dApps — including wallet connection,
> transaction signing, event handling, theming, and CSPR.cloud API
> access — across React (< 19 and 19+), Next.js, and Vanilla JS."
>
> — [docs.cspr.click/documentation/ai-agent-skills](https://docs.cspr.click/documentation/ai-agent-skills)

### Key Distinction

The **CSPR.click Web SDK** is a **browser-only** wallet aggregator. Every
signature requires a human to approve in their wallet UI (Casper Wallet
extension / WalletConnect / social-login wallet). It is NOT a
server-side signing service.

For **headless / autonomous agent workflows** (pytest e2e tests, MCP
server deploys, scheduled pipeline writes), the skill's reference
implementation ([Autarca](https://github.com/AK-Bit-Lab/Autarca)) uses
the same `casper-js-sdk` v5 that CSPR.click uses under the hood, but
loads the agent keypair from a server-side PEM file instead of a
browser wallet.

VaultWatch implements **both** patterns:

1. **Server-side agent wallet** (`agents/agent_wallet.py` +
   `scripts/csprclick_agent_wallet.cjs`) — programmatic keypair
   creation + signing for headless workflows.
2. **Browser-side CSPR.click Web SDK** (`dashboard/src/csprclick.js` +
   `dashboard/src/components/WalletBar.jsx`) — user-facing wallet
   connection + transaction approval.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VaultWatch Agent Wallet Stack                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────── Server-side ───────────────────┐  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  Python: vaultwatch.agents.agent_wallet.AgentWallet     │  │  │
│  │  │  ────────────────────────────────────────────────────── │  │  │
│  │  │  • ensure_exists()  → create or load agent wallet       │  │  │
│  │  │  • call_contract()  → sign + submit + verify deploy     │  │  │
│  │  │  • transfer_cspr()  → sign + submit + verify transfer   │  │  │
│  │  │  • refresh_balance() → query on-chain CSPR balance      │  │  │
│  │  │  • assert_funded()  → gate writes on minimum balance    │  │  │
│  │  └────────────────────────┬────────────────────────────────┘  │  │
│  │                           │ subprocess + JSON                  │  │
│  │  ┌────────────────────────▼────────────────────────────────┐  │  │
│  │  │  Node.js: scripts/csprclick_agent_wallet.cjs             │  │  │
│  │  │  ────────────────────────────────────────────────────── │  │  │
│  │  │  • create  → PrivateKey.generate(SECP256K1) → save PEM  │  │  │
│  │  │  • info    → load PEM, query balance via JSON-RPC        │  │  │
│  │  │  • public  → print agent public key (for CI scripts)     │  │  │
│  │  └────────────────────────┬────────────────────────────────┘  │  │
│  │                           │ casper-js-sdk v5                   │  │
│  │  ┌────────────────────────▼────────────────────────────────┐  │  │
│  │  │  Node.js: scripts/casper_call.cjs                        │  │  │
│  │  │  ────────────────────────────────────────────────────── │  │  │
│  │  │  • ContractCallBuilder  → stored-contract deploys        │  │  │
│  │  │  • NativeTransferBuilder → CSPR transfers                │  │  │
│  │  │  • Auto-loads agent wallet from $VAULTWATCH_AGENT_KEY_PATH│  │  │
│  │  │  • Signs + submits + verifies on Casper testnet/mainnet  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                               │  │
│  │  Key storage: $VAULTWATCH_AGENT_KEY_PATH                      │  │
│  │                (default: ~/.vaultwatch/agent_key.pem,         │  │
│  │                 mode 0600, gitignored — NEVER committed)      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────── Browser-side ──────────────────┐  │
│  │                                                               │  │
│  │  dashboard/src/csprclick.js                                   │  │
│  │  • CSPRClickProvider  → React context provider                │  │
│  │  • useClickRef()      → SDK ref (null until csprclick:loaded) │  │
│  │  • useActiveAccount() → tracks active wallet account          │  │
│  │  • Injects CSPR.click CDN script dynamically                  │  │
│  │                                                               │  │
│  │  dashboard/src/components/WalletBar.jsx                       │  │
│  │  • "Connect Wallet" button → ref.connect('casper-wallet')     │  │
│  │  • Account chip + Disconnect button → ref.disconnect()        │  │
│  │  • "Powered by CSPR.click" badge                              │  │
│  │                                                               │  │
│  │  CSPR.click Web SDK (CDN): https://cdn.cspr.click/ui/v2.1.0/  │  │
│  │  App ID: 'csprclick-template' (localhost dev — sanctioned)    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────── On-chain ──────────────────────┐  │
│  │                                                               │  │
│  │  Casper Testnet (casper-test)                                 │  │
│  │  • RPC: https://node.testnet.casper.network/rpc              │  │
│  │  • Faucet: https://testnet.cspr.live/tools/faucet            │  │
│  │  • Explorer: https://testnet.cspr.live                        │  │
│  │                                                               │  │
│  │  8 VaultWatch contracts (AuditTrail, RiskOracle,             │  │
│  │  SentinelCredit, SentinelRegistry, SentinelAlertLog,         │  │
│  │  AgentBehaviorIndex, RiskPolicyManager, SubscriberVault)     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Server-side: AgentWallet Abstraction

### Files

| File | Purpose |
| --- | --- |
| `agents/agent_wallet.py` | Python dataclass + classmethod constructors + subprocess wrappers |
| `scripts/csprclick_agent_wallet.cjs` | Node.js helper: `create`, `info`, `public` commands |
| `scripts/casper_call.cjs` | Node.js helper: `sign` + `submit` + `verify` (updated to auto-load agent wallet) |
| `skills/csprclick-skill/SKILL.md` | Official CSPR.click AI Agent Skill (installed verbatim from the make-software/csprclick-examples repo) |

### Key API: `AgentWallet`

```python
from vaultwatch.agents.agent_wallet import AgentWallet

# 1. Ensure an agent wallet exists (creates one on first run)
wallet = AgentWallet.ensure_exists()

# 2. Inspect it
print(wallet.public_key)        # '0203...'
print(wallet.account_hash)      # 'account-hash-...'
print(wallet.balance_cspr)      # 4308.32  (or None if unfunded)
print(wallet.funded)            # True / False

# 3. Sign + submit a stored-contract deploy
result = wallet.call_contract(
    contract_hash='cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932',
    entry_point='record_finding',
    args={
        'agent_name':   {'type': 'string', 'value': 'AnomalyAgent'},
        'confidence':   {'type': 'u8',     'value': '91'},
        'correction':   {'type': 'bool',   'value': 'false'},
        'block_height': {'type': 'u64',    'value': '1500000'},
    },
)
print(result['deploy_hash'])    # '67ff4ce5...'
print(result['success'])       # True

# 4. Sign + submit a native CSPR transfer
result = wallet.transfer_cspr(
    to_public_key='0203abc...',
    amount_motes=1_000_000_000,  # 1 CSPR
)

# 5. Assert the wallet is funded before a batch of writes
wallet.assert_funded(min_cspr=100.0)
```

### Key API: CLI

```bash
# Create a NEW agent wallet (programmatically generated SECP256K1 keypair)
node scripts/csprclick_agent_wallet.cjs create
# → {"ok": true, "public_key": "0203...", "account_hash": "account-hash-...",
#    "faucet_url": "https://testnet.cspr.live/tools/faucet", ...}

# Inspect the existing agent wallet (public key + balance)
node scripts/csprclick_agent_wallet.cjs info

# Print just the public key (for CI scripts)
node scripts/csprclick_agent_wallet.cjs public
```

### Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `VAULTWATCH_AGENT_KEY_PATH` | `~/.vaultwatch/agent_key.pem` | Path to the agent key PEM (gitignored) |
| `VAULTWATCH_AGENT_KEY_ALGO` | `secp256k1` | Key algorithm (`secp256k1` or `ed25519`) |
| `CASPER_RPC_URL` | `https://node.testnet.casper.network/rpc` | Casper RPC endpoint |
| `CASPER_CHAIN_NAME` | `casper-test` | Casper chain identifier |

### Backward Compatibility

The legacy `CasperContractClient(signing_key_path=...)` API still works —
it now accepts an optional `agent_wallet` parameter that takes
precedence over `signing_key_path`. Existing callers do not need to
change. The e2e test suite auto-discovers the agent wallet via (in
priority order):

1. `--e2e-signer-pem` CLI option
2. `$VAULTWATCH_AGENT_KEY_PATH` env var
3. `~/.vaultwatch/agent_key.pem` (default agent wallet path)
4. `<repo-root>/secret_key.pem` (legacy fallback for Account-2)
5. Auto-create a NEW agent wallet + print the faucet URL

---

## Browser-side: CSPR.click Web SDK

### Files

| File | Purpose |
| --- | --- |
| `dashboard/src/csprclick.js` | React context provider + hooks (`useClickRef`, `useActiveAccount`) |
| `dashboard/src/components/WalletBar.jsx` | Top-of-dashboard wallet connection bar |
| `dashboard/src/App.jsx` | Wraps root with `<CSPRClickProvider>` + renders `<WalletBar />` |
| `dashboard/index.html` | Adds `<div id="csprclick-ui"></div>` as the first child of `<body>` |

### CSPR.click SDK Constraints (all respected)

Per `skills/csprclick-skill/SKILL.md` "Key Constraints AI Must Respect":

- ✅ `clickSDKOptions` + `clickUIOptions` assigned to `window` BEFORE CDN injection
- ✅ `clickUIOptions` required with `uiContainer`, `rootAppElement`, `defaultTheme`, `accountMenuItems`
- ✅ No SDK methods called before `csprclick:loaded` fires
- ✅ CDN script injected dynamically (no static `<script>` tag in `index.html`)
- ✅ Disconnect button uses `ref.disconnect()` (not `ref.signOut()`)
- ✅ All `ref.on()` registrations torn down with `ref.off()` in `useEffect` return
- ✅ `appId: 'csprclick-template'` for localhost (sanctioned value)
- ✅ `<div id="csprclick-ui">` is the first child of `<body>`
- ✅ `casper-js-sdk >= 5.0.12` (we use 5.0.12)

---

## Workflow: First-time Setup

```bash
# 1. Create a NEW agent wallet (programmatic keypair generation)
cd vaultwatch
node scripts/csprclick_agent_wallet.cjs create
# Output:
# {
#   "ok": true,
#   "command": "create",
#   "created": true,
#   "key_path": "/home/user/.vaultwatch/agent_key.pem",
#   "key_algorithm": "secp256k1",
#   "public_key": "0203abc...",
#   "account_hash": "account-hash-...",
#   "faucet_url": "https://testnet.cspr.live/tools/faucet",
#   "next_step": "Fund this agent wallet at https://testnet.cspr.live/tools/faucet ..."
# }

# 2. Fund the wallet via the testnet faucet
# Open https://testnet.cspr.live/tools/faucet in a browser,
# paste the public key from step 1, and submit.

# 3. Verify the wallet is funded
node scripts/csprclick_agent_wallet.cjs info
# Output:
# {
#   "ok": true,
#   "command": "info",
#   "public_key": "0203abc...",
#   "balance_motes": 1000000000000,
#   "balance_cspr": 1000.0,
#   "funded": true,
#   ...
# }

# 4. Run the e2e suite (uses the agent wallet for all writes)
pytest tests/e2e/ --run-e2e
```

---

## Workflow: Existing Funded Account-2 Key

If you already have the funded Account-2 key at `vaultwatch/secret_key.pem`,
the agent wallet abstraction auto-discovers it:

```bash
# Option A: Set the env var explicitly
export VAULTWATCH_AGENT_KEY_PATH="$(pwd)/secret_key.pem"
pytest tests/e2e/ --run-e2e

# Option B: Let the auto-discovery find it (legacy fallback)
pytest tests/e2e/ --run-e2e
# The conftest.py fixture checks $VAULTWATCH_AGENT_KEY_PATH first,
# then ~/.vaultwatch/agent_key.pem, then <repo-root>/secret_key.pem.
```

---

## Verification

| Test | Result |
| --- | --- |
| Unit tests (`tests/unit/`) | ✅ 149 passed |
| Integration tests (`tests/integration/`) | ✅ 175 passed, 1 skipped |
| E2E read-only tests (`tests/e2e/test_network.py` + `test_contracts_on_chain.py`) | ✅ 58 passed (66s) |
| E2E real deploy (`test_sentinel_registry_register_real_deploy`) | ✅ 1 passed (11s) — agent wallet signed + submitted + verified on-chain |
| E2E payable deploy (`test_subscriber_vault_open_vault_real_deploy`) | ✅ 1 passed (11s) — agent wallet signed payable deploy + value transfer |
| Dashboard build (`npm run build`) | ✅ 40 modules transformed, no errors |

---

## References

- **CSPR.click AI Agent Skill (installed):** `skills/csprclick-skill/SKILL.md`
- **CSPR.click docs:** [docs.cspr.click](https://docs.cspr.click)
- **CSPR.click signing docs:** [docs.cspr.click/cspr.click-sdk/integration/signing-transactions](https://docs.cspr.click/cspr.click-sdk/integration/signing-transactions)
- **CSPR.click examples repo:** [github.com/make-software/csprclick-examples](https://github.com/make-software/csprclick-examples)
- **Casper AI Toolkit:** [casper.network/ai](https://www.casper.network/ai)
- **Casper JS SDK (v5):** [github.com/casper-ecosystem/casper-js-sdk](https://github.com/casper-ecosystem/casper-js-sdk)
- **Autarca (reference autonomous agent on Casper):** [github.com/AK-Bit-Lab/Autarca](https://github.com/AK-Bit-Lab/Autarca)
- **Casper testnet faucet:** [testnet.cspr.live/tools/faucet](https://testnet.cspr.live/tools/faucet)

---

## License

MIT (same as the rest of VaultWatch).
