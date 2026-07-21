# VaultWatch Demo Script — 3-5 Minute Buildathon Video

> Fix #17: Step-by-step demo video recording guide.

## Target Runtime: 3:30 — 4:30 minutes

---

## Pre-recording Checklist

- [ ] Terminal ready with VaultWatch repo open
- [ ] `.env` file configured with real `GROQ_API_KEY`, `CASPER_SIGNING_KEY_PATH`
- [ ] Browser open at https://dashboard-rho-amber-89.vercel.app
- [ ] Browser tab open at https://testnet.cspr.live
- [ ] Screen recording started (OBS/Loom/QuickTime)
- [ ] Font size: 18px minimum in terminal

---

## Scene 1: The Problem (0:00 — 0:30)

**Narration:**
> "DeFi protocols on Casper lose millions to rug pulls, oracle manipulation, and flash loan attacks — with no on-chain intelligence layer to stop them. VaultWatch changes that."

**Screen:** Show a DeFi hack headline or the dashboard anomaly feed

---

## Scene 2: Live Dashboard (0:30 — 1:15)

**Screen:** https://dashboard-rho-amber-89.vercel.app

**Narration:**
> "This is VaultWatch. Seven Groq-powered AI agents continuously monitor Casper for DeFi risk. Every finding is written to eight Odra smart contracts on Casper testnet — immutably, with on-chain timestamps."

**Actions:**
1. Point to live CSPR price (from CoinGecko)
2. Click "Scan Address" → type a test address → show AI risk classification in <2 seconds
3. Point to the Audit Trail panel → show real on-chain TX hashes

---

## Scene 3: x402 Payment Gate (1:15 — 2:00)

**Screen:** Terminal

```bash
# Show the x402 payment flow
curl -I http://localhost:8000/api/intel
# Expected: HTTP/1.1 402 Payment Required
# x402 payment params shown in response

# Now pay and retry
curl -H 'X-Payment: {"scheme":"casper-x402","paymentHash":"..."}'      http://localhost:8000/api/intel
# Expected: HTTP/1.1 200 OK with intelligence findings
```

```bash
# Full scripted demo — runs the complete x402 subscribe flow in <60 seconds
node scripts/demo_x402_subscribe.js
# Expected: Opens vault → deducts credit → queries intelligence → shows x402 receipt
```

**Narration:**
> "Intelligence is gated behind x402 micropayments. No payment → 402. With a valid x402 CSPR payment → instant access to risk intelligence. Every payment is verified on-chain against our SubscriberVault contract. The demo_x402_subscribe.js script runs the full flow in under 60 seconds."

---

## Scene 4: Contract Upgrade (2:00 — 2:45)

**Screen:** Split — terminal + https://testnet.cspr.live

```bash
# Demo: hot-swap risk policy without redeployment
python scripts/demo_upgrade_policy.py
```

**Narration:**
> "Watch this. We're upgrading the live risk thresholds — on Casper testnet — in 30 seconds. No contract redeployment. The RiskPolicyManager's upgrade_to_v2_rwa entry point changes the policy atomically. Agents immediately reclassify events at the new threshold. This is Casper's native upgradable contract capability."

**Actions:**
1. Run script → show deploy hash in terminal
2. Open deploy hash on testnet.cspr.live → show SUCCESS
3. Show new policy version number in the dashboard

---

## Scene 5: MCP Server (2:45 — 3:15)

**Screen:** Claude Desktop with VaultWatch MCP connected

**Narration:**
> "VaultWatch exposes all 20 intelligence tools via MCP — callable from any AI assistant that supports the Model Context Protocol. Watch Claude call our detect_anomaly tool live."

**Actions:**
1. Type in Claude: "Analyze this Casper address for DeFi risk: 0203cd..."
2. Claude calls `detect_anomaly` → shows real Groq response
3. Type: "Check the RiskPolicyManager contract on testnet"
4. Claude calls `verify_contract_deploy` → shows SUCCESS + explorer link

---

## Scene 6: Proof (3:15 — 3:45)

**Screen:** https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7

**Narration:**
> "All 8 contracts are verifiably deployed. Here's our deployer account — 16 named keys showing 8 contract installations plus 8 package references. Every deploy is independently verifiable. Here's the AuditTrail contract."

**Actions:**
1. Show deployer account page with 16 named keys
2. Click one contract → show deploy SUCCESS
3. Show `proof/PROOF.md` in the repo

---

## Scene 7: Close (3:45 — 4:00)

**Screen:** README.md top

**Narration:**
> "VaultWatch: compliance-gated, x402-paid, MCP-exposed DeFi risk intelligence — running natively on Casper. Open source. Live on testnet. Ready for mainnet."

---

## Recording Tips

- Use 1920×1080 minimum resolution
- 30fps minimum
- Add captions for accessibility
- Upload to YouTube (unlisted or public) and link in README
- Target file: `proof/demo_video.mp4` (or YouTube link)
