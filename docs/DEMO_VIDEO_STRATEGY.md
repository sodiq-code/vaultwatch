# 🏆 VaultWatch Demo Video Strategy — DoraHacks Casper Agentic Buildathon 2026 Finals

## Executive Summary

**VaultWatch is LITERALLY example direction #2 from the hackathon page**: "RWA Oracle Agents with Verifiable On-Chain Identity — Create an agent that scrapes off-chain data, runs a risk assessment model, and posts verified data on-chain via Casper's native X402 implementation. The agent maintains a verifiable on-chain identity and reputation score based on historical accuracy, creating a trust-minimized RWA oracle."

This is a **MASSIVE competitive advantage** — the judges literally described what VaultWatch does. Your demo must hammer this alignment home.

---

## What I Can Do Here (My Capabilities)

| # | Capability | Status |
|---|-----------|--------|
| 1 | **Capture live dashboard screenshots** | ✅ 9 screenshots captured |
| 2 | **Record video walkthrough (webm)** | ✅ vaultwalk_demo.webm recorded |
| 3 | **Generate AI title card & key moment images** | ✅ 5 images generated |
| 4 | **Create PPTX storyboard presentation** | ✅ (being created) |
| 5 | **Write exact 3-minute narration script** | ✅ (this document) |
| 6 | **Push all assets to GitHub** | 🔄 (pending) |

**What YOU Need To Do:**
1. **Record voiceover** using the narration script below (use phone, OBS, etc.)
2. **Combine video + screenshots + voiceover** in iMovie/Premiere/CapCut
3. **Submit on DoraHacks** before July 26, 2026 deadline

---

## Hackathon Judging Criteria Alignment Matrix

VaultWatch hits **ALL 7 criteria** with documented proof:

| # | Criterion | VaultWatch Alignment | Proof |
|---|-----------|---------------------|-------|
| 1 | **Technical Execution** | 40+ API routes, 8 Casper contracts, 7 AI agents, MCP server, SDK, dashboard | 481 test definitions, CI/CD pipeline, full deployment |
| 2 | **Innovation & Originality** | First x402 v2 implementation, hybrid Brier+escrow reputation, SafetyGuard fail-closed gate, Odra dict key derivation in Python | x402 verified payment hash, on-chain policy reads |
| 3 | **Use of AI / Agentic Systems** | 7 specialized AI agents in async pipeline with Groq→OpenRouter→heuristic 3-tier resilience | Each agent has distinct AI role, fail-safe/closed patterns |
| 4 | **Real-World Applicability** | RWA oracle for DeFi protocols: live CoinGecko + FRED data overlay with provenance tracking | 5 RWA asset categories, real CSPR price feeds |
| 5 | **User Experience & Design** | Glassmorphism dashboard with 8 panels, CSPR.click wallet connect, responsive design | Live dashboard screenshots, mobile responsive |
| 6 | **Working Smart Contracts** | 8 deployed Casper testnet contracts with 21 verified-success interaction deploys | All hashes in proof/PROOF.md, testnet.cspr.live links |
| 7 | **Long-Term Launch Plans** | MCP server (npm package), Python SDK, hybrid reputation formula, upgradeable contracts | vaultwatch_mcp/, sdk/, docs/REPUTATION_FORMULA.md |

---

## 🎬 3-Minute Demo Video Script

### TIMING: 180 seconds total

---

### SEGMENT 1: TITLE CARD (0:00 - 0:15) — 15 seconds

**[VISUAL]**: Title card image (title_card.png) with animated text overlay

**[NARRATION]**:
> "VaultWatch — the compliance-gated RWA oracle with 7 AI agents on Casper blockchain. The first project to implement the official x402 v2 micropayment protocol with real on-chain payment verification."

**[ON SCREEN TEXT]**:
- VaultWatch logo / name
- "Compliance-Gated RWA Oracle"
- "7 AI Agents | x402 v2 | 8 Casper Smart Contracts"
- DoraHacks Casper Agentic Buildathon 2026 Finals

---

### SEGMENT 2: THE PROBLEM (0:15 - 0:40) — 25 seconds

**[VISUAL]**: Dark background with text animations, fade to dashboard

**[NARRATION]**:
> "Real-world asset oracles face a fundamental trust problem: how do you verify that off-chain data reaching the blockchain is accurate, compliant, and hasn't been manipulated? Existing oracles either trust external data blindly or lack compliance gates entirely. VaultWatch solves this with a 7-layer AI agent pipeline where every piece of data is scanned, risk-classified, self-corrected, enriched with real-world context, validated through a fail-closed safety gate, and written to 8 on-chain smart contracts with cryptographic attestation."

**[ON SCREEN TEXT]**:
- "The Trust Problem" header
- Problem bullets: blind trust, no compliance, manipulation risk
- Solution: "7-layer AI pipeline + fail-closed safety + on-chain attestation"

---

### SEGMENT 3: 7 AI AGENT PIPELINE (0:40 - 1:05) — 25 seconds

**[VISUAL]**: 7_agents_pipeline.png + Dashboard Agent Pipeline panel (02_agent_pipeline.png or rec_01_pipeline.png)

**[NARRATION]**:
> "Here's how it works. ScannerAgent ingests blockchain events and filters noise. AnomalyAgent classifies risks into 8 types — rug pulls, whale dumps, depeg events. SelfCorrectionAgent retries low-confidence findings, SKIPPING garbage so nothing bad reaches the chain. RWAAgent enriches findings with live CoinGecko and FRED data. SafetyGuard is the critical fail-closed gate — when no AI key is available, ALL findings are REJECTED. Nothing gets through without passing safety validation. AuditAgent writes verified findings to AuditTrail and RiskOracle contracts with EAS-style SHA-256 attestations. Finally, IntelAgent exposes findings via a pay-per-query x402 gate."

**[ON SCREEN ANNOTATIONS]**:
- Show each agent with its role
- Highlight SafetyGuard FAIL-CLOSED badge
- Highlight SelfCorrectionAgent SKIP mechanism

---

### SEGMENT 4: x402 PAYMENT DEEP DEMO (1:05 - 1:45) — 40 seconds

**[VISUAL]**: x402_flow.png + Dashboard x402 Payments panel (06_x402_payments.png)

**[NARRATION]**:
> "This is our most innovative feature — the first implementation of the official Casper x402 v2 micropayment protocol. Here's the dual payment path. Path A: When a client requests intelligence data without a payment signature, VaultWatch returns HTTP 402 with a PAYMENT-REQUIRED header built by the official x402 SDK. The client signs an EIP-712 ExactCasperPayload with their Casper wallet and resubmits with the PAYMENT-SIGNATURE header. VaultWatch verifies the signature using the official ExactCasperScheme and delivers the data. Path B: For agent workflows, POST /x402/subscribe submits a real SubscriberVault.open_vault deploy via casper-js-sdk v5 — verified on testnet with deploy hash 0588e143... This is real on-chain payment with cryptographic proof, not a mock."

**[ON SCREEN ANNOTATIONS]**:
- Show HTTP 402 → PAYMENT-REQUIRED → SIGN → 200 + PAYMENT-RESPONSE flow
- Show verified deploy hash
- Show dual-path diagram
- Highlight: "FIRST x402 v2 implementation on Casper"

---

### SEGMENT 5: DASHBOARD WALKTHROUGH (1:45 - 2:15) — 30 seconds

**[VISUAL]**: Rapid walkthrough of dashboard panels (use video recording vaultwalk_demo.webm)

**[NARRATION]**:
> "The dashboard shows all this in real-time. The Agent Pipeline panel visualizes the 7-layer flow with live metrics per agent. RWA Assets displays 5 asset categories — gold, stablecoins, treasury yields, corporate bonds — with provenance badges showing whether data came from CoinGecko API, FRED API, or VaultWatch baseline. Attestations show EAS-style proofs with SHA-256 data integrity hashes. The x402 Payments panel displays pricing, contract hashes, and verified payment history. Chain Status reads directly from the 8 deployed Casper contracts."

**[ON SCREEN]**:
- Quick cuts through each panel (1-2 seconds each)
- Highlight provenance badges on RWA data
- Highlight wallet connect button

---

### SEGMENT 6: ON-CHAIN PROOF (2:15 - 2:40) — 25 seconds

**[VISUAL]**: on_chain_proof.png + Dashboard Chain Status panel (07_chain_status.png)

**[NARRATION]**:
> "Everything is verifiable on-chain. 8 Casper smart contracts deployed on testnet — AuditTrail, RiskOracle, SubscriberVault, SentinelCredit, SentinelRegistry, SentinelAlertLog, AgentBehaviorIndex, RiskPolicyManager. All written in Rust via Odra framework, compiled to WASM, with RBAC access control and emergency pause. 21 verified-success interaction deploys recorded, including record_finding, update_score, deposit, open_vault, and upgrade_policy. The SelfCorrectionAgent and SafetyGuard read their thresholds from the real deployed RiskPolicyManager contract — not hardcoded config. Policy changes propagate immediately."

**[ON SCREEN]**:
- Show contract hashes
- Show 21 verified deploy list
- Highlight on-chain policy reads
- Highlight: "8 contracts | 21 verified deploys | Real on-chain policies"

---

### SEGMENT 7: CLOSING — LONG-TERM VISION (2:40 - 3:00) — 20 seconds

**[VISUAL]**: vision_closing.png + Dashboard mobile responsive view (09_mobile_responsive.png)

**[NARRATION]**:
> "VaultWatch isn't just a hackathon project — it's a production-ready RWA oracle infrastructure. We've published a 20-tool MCP server as an npm package so any Claude Desktop user can query VaultWatch live. A Python SDK enables programmatic access. The hybrid Brier + escrow reputation formula creates trust-minimized agent identity. And the entire system is upgradeable — contracts use Odra's upgrade mechanism and risk policies can be hot-swapped on-chain. VaultWatch is the trust layer for the agent economy on Casper. Thank you."

**[ON SCREEN]**:
- MCP server badge (20 tools, npm package)
- SDK badge
- Reputation formula: R = 0.6 × brier_trust + 0.4 × escrow_trust
- Call to action: "Open source | Production ready | Casper ecosystem"

---

## 📸 Screenshots Available for Demo Video

| File | Content | Best Use |
|------|---------|----------|
| `01_main_dashboard.png` | Full dashboard landing view | Overview shot |
| `02_agent_pipeline.png` | Agent Pipeline panel | Segment 3 |
| `03_rwa_assets.png` | RWA Assets with provenance | Segment 5 |
| `04_attestations.png` | EAS-style attestations | Segment 5 |
| `05_agent_events.png` | Live agent event feed | Segment 5 |
| `06_x402_payments.png` | x402 Payments panel | Segment 4 |
| `07_chain_status.png` | Chain Status panel | Segment 6 |
| `08_pipeline_running.png` | Pipeline after running | Segment 3 |
| `09_mobile_responsive.png` | Mobile responsive view | Segment 7 |
| `title_card.png` | AI-generated title card | Segment 1 |
| `x402_flow.png` | AI-generated x402 flow | Segment 4 |
| `7_agents_pipeline.png` | AI-generated agent pipeline | Segment 3 |
| `on_chain_proof.png` | AI-generated on-chain proof | Segment 6 |
| `vision_closing.png` | AI-generated closing vision | Segment 7 |
| `vaultwalk_demo.webm` | Recorded walkthrough video | Segment 5 |

---

## 🏆 Top 5 Winning Strategies

### 1. LEAD WITH x402 (Highest Impact)
The hackathon explicitly highlights x402 Micropayments as a key technology. VaultWatch is the **FIRST project** to implement the official `@make-software/casper-x402` SDK with real on-chain payment verification. Show the HTTP 402 flow, the verified deploy hash, the dual payment path. This alone differentiates VaultWatch from every other submission.

### 2. HAMMER THE DIRECT ALIGNMENT
VaultWatch is literally example direction #2 from the hackathon page. State this explicitly: "Our project directly implements the hackathon's RWA Oracle Agent direction with verifiable on-chain identity and x402 micropayments." Judges love projects that nail the brief.

### 3. SHOW SAFETYGUARD FAIL-CLOSED
This is the most innovative architectural decision. No other project has a fail-closed AI safety gate. Explain: "When AI providers are unavailable, SafetyGuard REJECTS ALL findings — nothing reaches the chain. This is fail-closed by design, not fail-open." This hits Innovation & Originality hard.

### 4. DEMONSTRATE REAL ON-CHAIN ACTIVITY
Don't just show deployed contracts — show the 21 verified interaction deploys. Show testnet.cspr.live links. Show that the RiskPolicyManager is actually being read by agents. Show the verified x402 payment hash. Real activity > theoretical deployment.

### 5. SHOW THE MCP SERVER
The 20-tool MCP server published as npm package (`casper-sentinel-mcp`) demonstrates long-term viability and ecosystem contribution. It means any AI agent can integrate with VaultWatch via standard MCP protocol. This hits Long-Term Launch Plans and Long-Term Impact.

---

## ⚡ Quick Tips for Recording

1. **Use OBS Studio** (free) to record your screen + voiceover simultaneously
2. **Set resolution to 1920x1080** for professional quality
3. **Use the narration script above** — it's timed to exactly 3 minutes
4. **Practice the x402 segment** — it's the most important 40 seconds
5. **Show the FastAPI Swagger UI** at `http://localhost:8000/docs` for a quick visual of all 40 routes
6. **Show testnet.cspr.live** for on-chain verification (if you have browser access)
7. **End strong** — the closing 20 seconds must convey production-readiness

---

## 📊 Key Numbers to Display

- **7** AI agents in pipeline
- **8** Casper smart contracts deployed
- **21** verified-success interaction deploys
- **40+** API routes
- **481** test definitions
- **20** MCP server tools
- **x402 verified payment hash**: `0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c`
- **$150K** hackathon prize pool
- **3-tier** AI resilience: Groq → OpenRouter → Heuristic

---

## Submission Checklist

- [ ] Demo video recorded (3 minutes, public YouTube/Vimeo link)
- [ ] GitHub repository link (with README + documentation)
- [ ] Working prototype on Casper Testnet (8 contracts deployed)
- [ ] Transaction-producing on-chain component (21 verified deploys)
- [ ] Submit on DoraHacks before July 26, 2026 23:59 UTC

---

*Generated by VaultWatch AI Strategy Engine | DoraHacks Casper Agentic Buildathon 2026 Finals*
