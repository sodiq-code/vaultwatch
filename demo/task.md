# VaultWatch Demo Rebuild Task

## Goal
Rebuild demo video from the .mov source (4:35) → tight ≤3:10, narration perfectly synced to visual.

## Problems with current .mov
1. Too long (4:35, needs ≤3:10)
2. Flagged phrases to remove:
   - "a capability that does not exist anywhere else in this hackathon"
   - "DeFi to RWA bridge that institutional capital is waiting for"
   - Any other "unique in the hackathon" or personal/boastful claims
3. Narration doesn't match visuals — narrating one thing while showing another

## Source .mov Screen Timeline (mapped from frame analysis)
- 0:00–0:08   → Title card (VaultWatch, 130 Tests, 29 TX, Live)
- 0:08–0:55   → Dashboard: Risk Intelligence (query typing, "Analyzing via Groq...", results)
- 0:55–1:35   → Dashboard: Agent Pipeline Findings (CasperSwap CRITICAL, CasperLend HIGH, CasperYield HIGH)
- 1:35–2:05   → Dashboard: Anomaly Detection (risk score 42, anomalies flagged)
- 2:05–2:40   → Dashboard: RWA Assessment (US T-Bill, APPROVED, risk score 5/100)
- 2:40–3:05   → Dashboard: Live Feed (6 agents, events scrolling, x402 payment)
- 3:05–3:40   → Dashboard: Chain Status / Live Network Overview (block height, 8/8 contracts)
- 3:40–4:10   → Chain Status: Deployer account, deployed contracts table
- 4:10–4:35   → Outro / terminal (?)

## Strategy
Cut the .mov into segments, write tight script exactly matched to each segment's visual content,
generate voiceover, mix back. Target total = 190s (3:10).

## New Script Plan (segment-by-segment, total ~190s)

### [0:00–0:08] Title (8s)
"VaultWatch. Production-grade DeFi risk intelligence on Casper. Six AI agents. Eight deployed smart contracts."

### [0:08–0:55] Risk Intelligence Query (47s)  
Visual: typing query, agents analyzing, results appear
"The Risk Intelligence module accepts natural language queries. We ask: is the CSPR-USDT liquidity pool safe for a large position? Six agents activate simultaneously — Scanner, Anomaly, SelfCorrection, RWA, Intel, and Audit. The analysis runs in under three seconds. Confidence: ninety-one percent. Verdict: CRITICAL. The finding is written to the RiskOracle contract on Casper Testnet with a live transaction hash."

### [0:55–1:35] Agent Pipeline Findings (40s)
Visual: CasperSwap CRITICAL, CasperLend HIGH, CasperYield HIGH cards
"The Agent Pipeline shows findings across monitored protocols. CasperSwap: CRITICAL — top three wallets control sixty-eight percent of liquidity. Exit liquidity insufficient for positions above five hundred thousand. CasperLend: HIGH — collateral ratio at one point zero eight x, three positions at liquidation boundary. CasperYield: HIGH — fourteen times withdrawal volume surge in two hours. TVL down twenty-two percent."

### [1:35–2:05] Anomaly Detection (30s)
Visual: Anomaly Detection screen, score 42, two anomalies
"The Anomaly Detection module runs AnomalyAgent with a SelfCorrection feedback loop. CasperSwap scores forty-two out of one hundred — ELEVATED. Two anomalies flagged: low liquidity ratio and high volume-to-TVL ratio. The recommendation is written directly to the RiskOracle contract on Casper. Confidence: eighty-five percent."

### [2:05–2:40] RWA Assessment (35s)
Visual: US T-Bill, APPROVED verdict, risk score 5/100
"The RWA Assessment module evaluates real-world assets for on-chain tokenization. A US Treasury Bill — ninety-one day maturity, one point zero five collateral ratio, AAA credit rating. AI verdict: APPROVED. Risk score: five out of one hundred. The on-chain verdict is written to the AuditTrail contract."

### [2:40–3:05] Live Feed (25s)
Visual: Live Feed with 6 agents streaming events
"The Live Feed is the real-time event stream. Six active agents. Eight on-chain contracts. AuditAgent logs findings to AuditTrail. SelfCorrectionAgent re-evaluates low-confidence results. x402 payment processed — zero point five CSPR deducted from SubscriberVault. All eight contracts confirmed on-chain."

### [3:05–3:40] Chain Status (35s)
Visual: Chain Status, block height 8279525, 8/8 contracts, deployer account
"Chain Status shows the live Casper Testnet state. Block height eight million two hundred seventy-nine thousand five hundred twenty-five. Eight of eight Odra contracts deployed. CSPR price live from CoinGecko. All eight contracts deployed from a single verified account. Every deploy hash independently verifiable at testnet.cspr.live right now."

### [3:40–3:50] Outro (10s)
Visual: can loop Chain Status or title card
"One hundred thirty tests passing. Eight deployed contracts. Twenty-nine verified transaction hashes. VaultWatch. Production-ready. On-chain. Live."

## Total target: ~230s narration words → ~190s at moderate pace ✓

## Steps
1. [ ] Cut .mov into segments with exact timestamps
2. [ ] Write final tight script (no flagged phrases)
3. [ ] Generate voiceover
4. [ ] Verify voiceover duration ≈ video duration
5. [ ] Mix audio onto video
6. [ ] Verify output ≤ 3:10
7. [ ] Spot-check visual/narration sync
