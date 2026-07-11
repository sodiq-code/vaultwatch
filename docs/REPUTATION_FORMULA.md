# VaultWatch Hybrid Reputation Formula

> **VaultWatch's signature primitive** — a hybrid reputation formula that
> combines two independent trust signals into one score.

## TL;DR

VaultWatch publishes a **hybrid reputation formula** that combines two
independent trust signals into one score:

```
R = w_B · (100 − Brier_normalized) + w_E · escrow_trust
```

| Component | Source | Weight (default) | What it measures |
|-----------|--------|------------------|------------------|
| **Brier** | `AgentBehaviorIndex` on-chain metrics | 0.6 | AI agent prediction accuracy over time |
| **Escrow** | `SentinelCredit` + `SubscriberVault` on-chain state | 0.4 | Economic stake + slash history |

Both the Brier and escrow approaches are established reputation primitives.
VaultWatch's contribution is combining both in a single formula — reflecting
that AI accuracy is the core value but economic stake is the backstop. Every
component is verifiable on-chain via Casper RPC.

---

## 1. Why Hybrid?

The Brier score and escrow-derived trust are two established approaches to
measuring reputation. Each captures an important but incomplete signal:

- **Brier-scored reputation** rigorously measures prediction quality but
  doesn't account for economic stake — an agent with no "skin in the game"
  can still score high.
- **Escrow-derived reputation** ties trust to real economic stake but says
  nothing about the agent's accuracy or prediction quality.

VaultWatch's thesis: a trustworthy intelligence system needs **both**.
The hybrid formula captures both failure modes in a single score.

---

## 2. The Brier Component

### 2.1 Raw Brier Score

For a set of N binary predictions with predicted probabilities `p_i` and
realized outcomes `o_i ∈ {0, 1}`:

```
Brier = (1/N) · Σ (p_i − o_i)²
```

Range: `[0, 2]` for binary outcomes (0 = perfect, 1 = random, 2 = perfectly wrong).

### 2.2 EWMA Decay

Old predictions should count less. VaultWatch uses exponentially-weighted
moving average with λ = 0.92:

```
Brier_ewma = Σ w_i · (p_i − o_i)²  /  Σ w_i
where w_i = λ^(N−1−i)   (most recent → w = 1)
```

At λ = 0.92, a prediction 10 cycles ago carries 0.92¹⁰ ≈ 43% weight.
This matches Pantheon's decay constant.

### 2.3 Normalization to [0, 100]

```
brier_trust = 100 · (1 − Brier_ewma / 2)
```

| Raw Brier | Meaning | brier_trust |
|-----------|---------|-------------|
| 0.0 | Perfect predictions | 100 |
| 0.5 | Random guessing | 50 |
| 1.0 | Always wrong, confidently | 0 |
| 2.0 | Perfectly anti-correlated | 0 |

### 2.4 On-chain Source

The `AgentBehaviorIndex` contract stores cumulative counters per agent:
- `total_decisions`
- `high_confidence_count` (confidence ≥ 80)
- `corrections_applied` (SelfCorrection re-ran)
- `safety_rejections` (SafetyGuard blocked)
- `avg_confidence` (rolling)

We **reconstruct** a representative prediction history from these aggregates
(see `agents/reputation.py::predictions_from_agent_metrics`). This is
documented as the "aggregate reconstruction" method. For full precision,
a future contract upgrade could store a rolling prediction log on-chain.

---

## 3. The Escrow Component

### 3.1 Formula

```
escrow_trust = 30 + log10(escrowed_balance_motes + 1) · 6.67
              − min(40, slash_count · 10)
              + min(20, successful_queries)
              − min(15, disputed_queries · 5)
```

| Term | Meaning | Range |
|------|---------|-------|
| Base | Neutral starting trust | +30 |
| Stake | Log-scaled escrow (1 CSPR ≈ +60 pts, 1000 CSPR ≈ +80, 1M CSPR ≈ +100) | 0 to +60 |
| Slash penalty | −10 per slash, capped at −40 | −40 to 0 |
| Query bonus | +1 per successful query, capped at +20 | 0 to +20 |
| Dispute penalty | −5 per dispute, capped at −15 | −15 to 0 |

Final escrow_trust clamped to `[0, 100]`.

### 3.2 On-chain Sources

| Field | Contract | Entry point |
|-------|----------|-------------|
| `escrowed_balance_motes` | `SubscriberVault` | `get_balance(address)` |
| `total_deposited_motes` | `SentinelCredit` | `get_account(address).total_deposited` |
| `slash_count` | `AgentBehaviorIndex` | `get_metrics(agent).safety_rejections` |
| `successful_queries` | `SentinelCredit` | `get_account(address).query_count` |
| `disputed_queries` | (future) `AuditTrail` | `get_disputes(address)` |

### 3.3 Why log-scaled stake?

Linear stake favors whales: a 1M CSPR depositor would dominate a 100 CSPR
depositor regardless of accuracy. Log-scaling preserves signal across 6
orders of magnitude while still rewarding larger commitments.

---

## 4. The Hybrid Combination

### 4.1 Default Weights

```
w_B = 0.6   (Brier / AI accuracy)
w_E = 0.4   (Escrow / economic stake)
```

**Rationale:** VaultWatch's core value is AI intelligence — so the Brier
component weighs higher. Escrow is the backstop, not the primary signal.
Weights are tunable per-query via the `reputation_query` MCP tool.

### 4.2 Tiers

| Score | Tier | Meaning |
|-------|------|---------|
| ≥ 85 | PLATINUM | Top-tier trust; eligible for premium integrations |
| 70–84 | GOLD | Strong trust; standard integrations |
| 50–69 | SILVER | Acceptable; monitored |
| < 50 | BRONZE | Low trust; rate-limited or quarantined |

### 4.3 Example Calculation

Consider `AnomalyAgent` with on-chain metrics:
- `total_decisions = 100`
- `high_confidence_count = 70` (70% of decisions ≥ 80 confidence)
- `corrections_applied = 5`
- `safety_rejections = 2`
- `avg_confidence = 85`

And escrow stake:
- `escrowed_balance = 50 CSPR = 50_000_000_000 motes`
- `slash_count = 0`
- `successful_queries = 100`
- `disputed_queries = 0`

**Brier:**
- Reconstructed predictions: 70 @ (0.85, 1.0), 5 @ (0.70, 0.0), 2 @ (0.60, 0.0), 23 @ (0.85, 0.5)
- Raw Brier ≈ 0.082
- `brier_trust = 100 · (1 − 0.082/2) = 95.9`

**Escrow:**
- `stake_pts = min(60, log10(5e10 + 1) · 6.67) = min(60, 71.9) = 60`
- `slash_penalty = 0`
- `query_bonus = min(20, 100) = 20`
- `dispute_penalty = 0`
- `escrow_trust = 30 + 60 − 0 + 20 − 0 = 110 → clamped to 100`

**Hybrid:**
- `R = 0.6 · 95.9 + 0.4 · 100 = 57.5 + 40 = 97.5`
- **Tier: PLATINUM**

---

## 5. Implementation

The formula is implemented in `agents/reputation.py`:

```python
from agents.reputation import reputation_for_agent, EscrowStake

result = reputation_for_agent(
    agent_name="AnomalyAgent",
    agent_metrics={
        "total_decisions": 100,
        "high_confidence_count": 70,
        "corrections_applied": 5,
        "safety_rejections": 2,
        "avg_confidence": 85,
    },
    escrow_stake=EscrowStake(
        address="AnomalyAgent",
        escrowed_balance_motes=50_000_000_000,
        total_deposited_motes=50_000_000_000,
        total_spent_motes=5_000_000_000,
        slash_count=0,
        successful_queries=100,
        disputed_queries=0,
    ),
)
# → {"reputation_score": 97.5, "tier": "PLATINUM", ...}
```

Exposable via MCP:

```python
# In Claude Desktop or any MCP client:
result = await mcp.call_tool("reputation_query", {
    "address": "AnomalyAgent",
    "w_brier": 0.6,
    "w_escrow": 0.4,
})
```

---

## 6. Verification

Every component of the formula is verifiable on-chain:

```bash
# 1. Get agent metrics from AgentBehaviorIndex
casper-client query-state --node-url https://rpc.testnet.casper.network \
  -k <AGENT_BEHAVIOR_INDEX_HASH> --path 'metrics/AnomalyAgent'

# 2. Get escrow balance from SubscriberVault
casper-client query-state --node-url https://rpc.testnet.casper.network \
  -k <SUBSCRIBER_VAULT_HASH> --path 'accounts/<address>'

# 3. Get credit account from SentinelCredit
casper-client query-state --node-url https://rpc.testnet.casper.network \
  -k <SENTINEL_CREDIT_HASH> --path 'accounts/<address>'
```

The `reputation_query` MCP tool returns every input it used, so a judge
can recompute the score by hand from on-chain state.

---

## 7. Approach Comparison

| Dimension | Brier-only | Escrow-only | VaultWatch (hybrid) |
|-----------|------------|-------------|---------------------|
| Formula type | Brier (EWMA) | Escrow-derived | Hybrid (Brier + escrow) |
| Red-team checklist | varies | varies | 12 checks (see RED_TEAM_CHECKLIST.md) |
| On-chain source | On-chain predictions | Off-chain registry | On-chain (AgentBehaviorIndex + SentinelCredit + SubscriberVault) |
| Tunable weights | No | No | Yes (per-query via MCP) |
| AI accuracy signal | Yes | No | Yes |
| Economic stake signal | No | Yes | Yes |

---

## 8. Limitations & Future Work

1. **Aggregate reconstruction** — we reconstruct predictions from cumulative
   counters, not a full log. A contract upgrade storing a rolling prediction
   buffer would give exact Brier scores.
2. **No slashing yet** — `slash_count` is wired in the formula but the
   slashing trigger (who decides an agent was wrong?) is a future governance
   module. For now, `safety_rejections` is a proxy.
3. **Dispute resolution** — `disputed_queries` is a placeholder; a
   dispute-resolution contract would need to be added for full rigor.
4. **Weight tuning** — defaults (0.6/0.4) are reasonable but empirical
   tuning would require a labeled dataset of agent decisions.

These are honest limitations. The Brier-only and escrow-only approaches have
analogous gaps (Brier-only doesn't measure economic stake; escrow-only doesn't
measure AI accuracy).
