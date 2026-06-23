/**
 * VaultWatch Mock API
 * Provides realistic demo data when the backend is offline.
 * Used for hosted demos (Vercel) without a live Python API.
 */

const MOCK_DELAY = () => new Promise(r => setTimeout(r, 400 + Math.random() * 600))

const FINDINGS = [
  {
    id: 'F-001',
    protocol: 'CasperSwap',
    summary: 'Whale concentration detected — top 3 wallets hold 68% of liquidity pool',
    severity: 'CRITICAL',
    risk_type: 'whale_concentration',
    confidence: 0.91,
    tx_hash: '27249e7838f2b14443ebd3b0aa461608675e36e6ef3a954af431b5f2df8041fb',
    timestamp: Date.now() - 120000,
  },
  {
    id: 'F-002',
    protocol: 'CasperLend',
    summary: 'Collateral ratio dropped below 1.1x threshold — liquidation risk elevated',
    severity: 'HIGH',
    risk_type: 'collateral_risk',
    confidence: 0.87,
    tx_hash: '68ef325d2b3a0f544467d8624e5042e428cd40258009777ffcdc568c1f426c55',
    timestamp: Date.now() - 360000,
  },
  {
    id: 'F-003',
    protocol: 'CasperYield',
    summary: 'Abnormal withdrawal spike — 14x volume increase in 2-hour window',
    severity: 'HIGH',
    risk_type: 'withdrawal_spike',
    confidence: 0.83,
    tx_hash: 'b6466009e65ac07a7ab7a26b3c5f0f600a6dc4c1efeaf96ea105000d24c8e6d9',
    timestamp: Date.now() - 720000,
  },
  {
    id: 'F-004',
    protocol: 'CasperSwap',
    summary: 'Price impact exceeds 5% on CSPR/USDC pair — low liquidity warning',
    severity: 'MEDIUM',
    risk_type: 'low_liquidity',
    confidence: 0.79,
    tx_hash: '71398513bc183652549d46f4ea3d5319a7614cc55ce6c5378302150e46b07562',
    timestamp: Date.now() - 1200000,
  },
  {
    id: 'F-005',
    protocol: 'CasperDEX',
    summary: 'Governance token distribution: 72% held by 1 address — centralization risk',
    severity: 'MEDIUM',
    risk_type: 'centralization',
    confidence: 0.76,
    tx_hash: '8f762ab42f0da419ace4d99259893165a8483ad376d524b15ba76355cb597693',
    timestamp: Date.now() - 1800000,
  },
]

const AUDIT_ENTRIES = [
  { id: 1, action: 'scan_complete', actor: 'ScannerAgent', details: 'Scanned CasperSwap — 3 anomalies found' },
  { id: 2, action: 'finding_written', actor: 'AuditAgent', details: 'F-001 written to AuditTrail.rs on Casper testnet' },
  { id: 3, action: 'risk_score_updated', actor: 'AuditAgent', details: 'RiskOracle.rs updated — CasperSwap score: 87/100' },
  { id: 4, action: 'alert_dispatched', actor: 'IntelAgent', details: 'CRITICAL alert sent to 3 subscribers via SentinelAlertLog' },
  { id: 5, action: 'self_correction', actor: 'SelfCorrectionAgent', details: 'Low-confidence finding (0.62) re-evaluated → SKIP' },
  { id: 6, action: 'rwa_assessed', actor: 'RWAAgent', details: 'US T-Bill 2026-001 assessed via Groq Compound — APPROVED' },
  { id: 7, action: 'policy_updated', actor: 'RiskPolicyManager', details: 'Risk threshold updated: 0.75 → 0.60 on testnet' },
  { id: 8, action: 'x402_payment', actor: 'IntelAgent', details: 'x402 query paid — 0.5 CSPR deducted from SubscriberVault' },
  { id: 9, action: 'scan_complete', actor: 'ScannerAgent', details: 'Scanned CasperLend — 1 anomaly found' },
  { id: 10, action: 'finding_written', actor: 'AuditAgent', details: 'F-002 written to AuditTrail.rs on Casper testnet' },
]

const OTEL_SPANS = [
  { name: 'ScannerAgent.scan', duration_ms: 312.4, status: 'OK' },
  { name: 'AnomalyAgent.classify', duration_ms: 891.2, status: 'OK' },
  { name: 'SelfCorrectionAgent.evaluate', duration_ms: 743.1, status: 'OK' },
  { name: 'SafetyGuard.check', duration_ms: 42.8, status: 'OK' },
  { name: 'AuditAgent.write_to_chain', duration_ms: 1204.7, status: 'OK' },
  { name: 'IntelAgent.dispatch_alert', duration_ms: 287.3, status: 'OK' },
  { name: 'RWAAgent.assess', duration_ms: 1847.6, status: 'OK' },
  { name: 'ScannerAgent.scan', duration_ms: 298.5, status: 'OK' },
]

const DEPLOY_HASHES = {
  AuditTrail: '27249e7838f2b14443ebd3b0aa461608675e36e6ef3a954af431b5f2df8041fb',
  RiskOracle: '68ef325d2b3a0f544467d8624e5042e428cd40258009777ffcdc568c1f426c55',
  SentinelCredit: 'b6466009e65ac07a7ab7a26b3c5f0f600a6dc4c1efeaf96ea105000d24c8e6d9',
  SentinelRegistry: '71398513bc183652549d46f4ea3d5319a7614cc55ce6c5378302150e46b07562',
  SentinelAlertLog: '8f762ab42f0da419ace4d99259893165a8483ad376d524b15ba76355cb597693',
  AgentBehaviorIndex: '665c1bd2937f88403806a1e3cd4fc9de7b931baa6cbc9b87bd05b6b23d823171',
  RiskPolicyManager: '14284d5c3f3acf47dab65df94bbe982cdc787ff38245154521810f7cf819d874',
  SubscriberVault: '2fb6b5b699216d4662701b9d54101bb3740b3a10c62d8f7aaf5f0703a7a1b009',
}

let _blockHeight = 2847391
let _lastBlock = Date.now()

function getBlockHeight() {
  const elapsed = (Date.now() - _lastBlock) / 1000
  _blockHeight += Math.floor(elapsed / 30) // ~1 block per 30s on Casper
  _lastBlock = Date.now()
  return _blockHeight
}

export const mockApi = {
  async health() {
    await MOCK_DELAY()
    return { status: 'ok', version: '4.0.0', mode: 'demo', agents: 6, contracts: 8 }
  },

  async getBlock() {
    await MOCK_DELAY()
    return { block_height: getBlockHeight(), network: 'casper-test', timestamp: new Date().toISOString() }
  },

  async riskQuery({ query, protocol }) {
    await MOCK_DELAY()
    const riskFactors = [
      'Whale concentration above safe threshold (68% by top 3 wallets)',
      'Liquidity depth insufficient for large exits (>$500k)',
      'No time-lock on governance — immediate execution risk',
    ]
    return {
      result: {
        summary: `AI risk analysis for ${protocol || 'the queried protocol'}: Based on live Casper testnet data and Groq Compound intelligence, the protocol shows elevated risk indicators. ${query.includes('collateral') ? 'Collateral ratios are trending downward.' : 'Whale activity is the primary concern.'}`,
        risk_factors: riskFactors,
        confidence: 0.89,
        groq_model: 'llama-3.3-70b-versatile',
        on_chain_hash: DEPLOY_HASHES.RiskOracle,
      }
    }
  },

  async getFindings(limit = 20) {
    await MOCK_DELAY()
    return { findings: FINDINGS.slice(0, limit), total: FINDINGS.length }
  },

  async detectAnomaly(metrics) {
    await MOCK_DELAY()
    const tvl = parseFloat(metrics.tvl) || 0
    const vol = parseFloat(metrics.volume_24h) || 0
    const priceChange = parseFloat(metrics.price_change_1h) || 0
    const liqRatio = parseFloat(metrics.liquidity_ratio) || 1

    const anomalies = []
    let score = 0

    if (vol / tvl > 0.4) { anomalies.push('high_volume_ratio'); score += 25 }
    if (Math.abs(priceChange) > 5) { anomalies.push('price_volatility'); score += 20 }
    if (liqRatio < 0.5) { anomalies.push('low_liquidity'); score += 30 }
    if (tvl < 1000000) { anomalies.push('low_tvl'); score += 15 }
    score = Math.min(score + Math.floor(Math.random() * 15), 99)

    return {
      risk_score: score,
      anomalies,
      recommendation: score > 70
        ? 'CRITICAL: Immediate monitoring required. Consider pausing new deposits.'
        : score > 40
        ? 'ELEVATED: Monitor closely. Implement additional safeguards.'
        : 'Protocol metrics within normal parameters. Continue standard monitoring.',
      agent: 'AnomalyAgent (llama-3.3-70b-versatile)',
      confidence: 0.83 + Math.random() * 0.12,
    }
  },

  async assessRWA(asset) {
    await MOCK_DELAY()
    const ratio = parseFloat(asset.collateral_ratio) || 1
    const days = parseInt(asset.maturity_days) || 90
    const rating = asset.credit_rating || 'BBB'
    const isGoodRating = ['AAA', 'AA+', 'AA', 'AA-', 'A+'].includes(rating)
    const verdict = ratio >= 1.0 && isGoodRating && days <= 365 ? 'APPROVED' : ratio < 0.9 ? 'REJECTED' : 'REVIEW'
    return {
      assessment: {
        verdict,
        risk_score: verdict === 'APPROVED' ? Math.floor(Math.random() * 25 + 10) : Math.floor(Math.random() * 40 + 55),
        notes: verdict === 'APPROVED'
          ? `${asset.asset_type} meets collateral requirements. Groq Compound web intelligence confirms issuer creditworthiness. Suitable for on-chain tokenisation on Casper.`
          : `Asset fails minimum collateral requirements (${ratio}x vs 1.0x required). Review collateral structure before resubmission.`,
        groq_model: 'compound-beta',
      }
    }
  },

  async getRWAAssets() {
    await MOCK_DELAY()
    return {
      assets: [
        { asset_id: 'us-tbill-2026-001', asset_type: 'treasury_bill', verdict: 'APPROVED' },
        { asset_id: 'corp-bond-acme-2027', asset_type: 'corporate_bond', verdict: 'REVIEW' },
        { asset_id: 'solar-farm-tx-001', asset_type: 'real_estate', verdict: 'APPROVED' },
      ]
    }
  },

  async getAuditLog(limit = 50) {
    await MOCK_DELAY()
    return { entries: AUDIT_ENTRIES.slice(0, limit), total: AUDIT_ENTRIES.length }
  },

  async writeAudit({ action, actor, details }) {
    await MOCK_DELAY()
    const hash = Array.from({length: 64}, () => '0123456789abcdef'[Math.floor(Math.random()*16)]).join('')
    return { success: true, deploy_hash: hash, block_height: getBlockHeight() }
  },

  async getSpans() {
    await MOCK_DELAY()
    return { spans: OTEL_SPANS }
  },

  deployHashes: DEPLOY_HASHES,
  blockHeightFn: getBlockHeight,
}
