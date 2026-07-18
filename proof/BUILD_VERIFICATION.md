# VaultWatch — Build Verification Artifacts

> Fix #21: Replacing human-written summaries with verifiable build outputs.

## Compilation Environment

```
rustc 1.81.0-nightly (nightly-2024-07-25)
cargo 1.81.0-nightly
odra 2.8.0
wasm-opt 119
target: wasm32-unknown-unknown
profile: release (-C opt-level=z -C lto=fat)
bulk-memory: DISABLED (-C target-feature=-bulk-memory)
```

## WASM Artifacts — File Sizes

| Contract | WASM File | Size (bytes) | Size (KB) |
|----------|-----------|--------------|----------|
| AuditTrail | AuditTrail.wasm | 136,982 | 133.8 |
| AgentBehaviorIndex | AgentBehaviorIndex.wasm | 136,073 | 132.9 |
| RiskOracle | RiskOracle.wasm | 135,158 | 132.0 |
| RiskPolicyManager | RiskPolicyManager.wasm | 136,174 | 133.0 |
| SentinelAlertLog | SentinelAlertLog.wasm | 137,834 | 134.6 |
| SentinelCredit | SentinelCredit.wasm | 139,563 | 136.3 |
| SentinelRegistry | SentinelRegistry.wasm | 136,716 | 133.5 |
| SubscriberVault | SubscriberVault.wasm | 139,352 | 136.1 |

**Total WASM size: ~1.1 MB for 8 contracts**

## Bulk-Memory Opcode Verification

All contracts verified SAFE — zero bulk-memory opcodes (memory.copy, memory.fill, memory.init).

```bash
$ python scripts/check_wasm_bulk_memory.py contracts/wasm/
Checking AuditTrail.wasm ... SAFE (0 bulk-memory opcodes)
Checking AgentBehaviorIndex.wasm ... SAFE (0 bulk-memory opcodes)
Checking RiskOracle.wasm ... SAFE (0 bulk-memory opcodes)
Checking RiskPolicyManager.wasm ... SAFE (0 bulk-memory opcodes)
Checking SentinelAlertLog.wasm ... SAFE (0 bulk-memory opcodes)
Checking SentinelCredit.wasm ... SAFE (0 bulk-memory opcodes)
Checking SentinelRegistry.wasm ... SAFE (0 bulk-memory opcodes)
Checking SubscriberVault.wasm ... SAFE (0 bulk-memory opcodes)

All 8 contracts: BULK-MEMORY SAFE ✅
```

## Contract Entry Points

### AuditTrail
- `init()` — Initialization
- `record_finding(address, risk_type, severity, confidence, description) → u64`
- `get_finding(id) → Finding`
- `finding_count() → u64`
- `transfer_ownership(new_owner)`

### RiskPolicyManager
- `init()` — Initialization
- `update_policy(min_confidence_threshold, critical_score_threshold, high_score_threshold, medium_score_threshold, max_retry_count, safety_rejection_threshold)`
- `upgrade_to_v2_rwa(rwa_confidence_boost, rwa_critical_threshold)` ← **NEW v2 entry point**
- `get_current_policy() → RiskPolicy`
- `get_policy_version(version) → Option<RiskPolicy>`
- `grant_operator(account)`
- `grant_admin(account)`
- `revoke_operator(account)`

### SentinelCredit
- `init(query_price, premium_price)` — Initialization
- `deposit(account_address)` ← **#[odra(payable)] — accepts real CSPR**
- `deduct_credit(account_address, query_type) → bool`
- `withdraw(amount, to)` ← **NEW — revenue withdrawal**
- `get_balance(account_address) → U512`
- `get_query_price() → U512`
- `total_revenue() → U512`

### SentinelAlertLog
- `init()` — Initialization
- `log_alert(subscriber_address, finding_id, severity, risk_type, block_height, timestamp, delivered) → u64`
- `get_address_logs(subscriber_address) → Vec<u64>` ← **Fixed: was String**
- `get_log(log_id) → AlertRecord`
- `log_count() → u64`

### SentinelRegistry, AgentBehaviorIndex, RiskOracle, SubscriberVault
See contract source in `contracts/src/`.

## Deployed Contract Hashes (Casper Testnet)

All 8 deployments verified SUCCESS on testnet.cspr.live:

| Contract | Deploy Hash | Status |
|----------|-------------|--------|
| AuditTrail | b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6336a7 | ✅ SUCCESS |
| SentinelRegistry | 9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c | ✅ SUCCESS |
| RiskOracle | e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d | ✅ SUCCESS |
| SentinelCredit | 0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71 | ✅ SUCCESS |
| AgentBehaviorIndex | 05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0 | ✅ SUCCESS |
| SentinelAlertLog | 53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925 | ✅ SUCCESS |
| RiskPolicyManager | 93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e | ✅ SUCCESS |
| SubscriberVault | 6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d | ✅ SUCCESS |

Deployer account: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`
[View on testnet.cspr.live →](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7)
