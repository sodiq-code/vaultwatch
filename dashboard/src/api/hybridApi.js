/**
 * VaultWatch Hybrid API — Real data first, mock fallback with provenance.
 *
 * Strategy:
 *   1. Try live API call (liveApi.js functions)
 *   2. On failure: fall back to mock generators (inline, NOT importing mockApi.js)
 *   3. Track source: 'live' | 'fallback' | 'cache' so UI can badge data provenance
 *   4. Keep ALL the same function signatures as current liveApi object in App.jsx
 *
 * Every wrapped function returns { ...data, _source: 'live'|'fallback'|'cache' }
 */

import {
  fetchCSPRPrice,
  fetchCSPRPriceHistory,
  fetchNetworkInfo,
  fetchAccountDeploys,
  fetchLiveFindings,
  fetchFinding,
  fetchRiskScore,
  liveRiskQuery,
  liveDetectAnomaly,
  liveAssessRWA,
  liveHealth,
  CONTRACT_HASHES,
  CONTRACT_PACKAGE_HASHES,
  DEPLOYER_ACCOUNT,
  getLiveBlockHeight,
  SEED_FINDINGS,
} from '../liveApi.js'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

// ─── Helper: wrap async fn with fallback ───
function withFallback(asyncFn, fallbackFn, sourceOnSuccess = 'live', sourceOnFallback = 'fallback') {
  return async (...args) => {
    try {
      const result = await asyncFn(...args)
      if (result !== null && result !== undefined) {
        return { ...result, _source: sourceOnSuccess }
      }
    } catch (e) {
      // Fall through to fallback
    }
    const fallback = fallbackFn(...args)
    return { ...fallback, _source: sourceOnFallback }
  }
}

// ─── Mock generators (inline — replaces mockApi.js) ───

function mockRiskResult(query) {
  return {
    result: {
      summary: `Risk analysis (fallback): ${query?.slice(0, 80) || 'general query'}`,
      risk_factors: ['whale_concentration', 'collateral_drop', 'liquidity_risk'],
      confidence: 0.78,
      on_chain_link: `https://testnet.cspr.live/contract/${CONTRACT_HASHES.RiskOracle}`,
    },
  }
}

function mockAnomalyResult(metrics) {
  const score = Math.min(100, Math.max(0, Math.round(
    (metrics?.price_impact_pct || 2) * 10 +
    (metrics?.volume_change_pct || 0) * 0.5 +
    (metrics?.whale_pct || 0) * 0.3
  )))
  return {
    anomaly_score: score,
    anomaly_tags: score > 70 ? ['whale_dump', 'price_manipulation'] : score > 40 ? ['volume_spike'] : ['normal_activity'],
    recommendation: score > 70 ? 'CRITICAL: Immediate investigation required' : score > 40 ? 'Monitor closely' : 'Normal activity observed',
    self_correction: false,
  }
}

function mockRWAResult(asset) {
  const score = Math.round(Math.random() * 30 + 40)
  return {
    verdict: score > 80 ? 'REJECTED' : score > 60 ? 'REVIEW' : 'APPROVED',
    risk_score: score,
    notes: `RWA assessment (fallback) for ${asset?.asset_id || 'unknown'}: ${asset?.asset_type || 'unknown'} type asset. Mock evaluation pending live data.`,
    risk_factors: ['valuation_uncertainty', 'market_volatility', 'regulatory_risk'],
  }
}

function mockAuditLog(limit) {
  const actions = ['risk_query', 'anomaly_detect', 'rwa_assess', 'audit_write', 'self_correction', 'alert_dispatch', 'vault_subscribe', 'policy_update', 'finding_record', 'attestation_post']
  return Array.from({ length: limit || 10 }, (_, i) => ({
    id: i + 1,
    action: actions[i % actions.length],
    actor: `agent-${actions[i % actions.length].split('_')[0]}`,
    details: `Mock audit entry #${i + 1}`,
    timestamp: Date.now() - i * 120_000,
    deploy_hash: `0x${Array.from({length:64}, ()=> Math.floor(Math.random()*16).toString(16)).join('')}`,
  }))
}

function mockSpans() {
  return [
    { spanId: 's1', name: 'scanner.scan', durationMs: 120, status: 'OK' },
    { spanId: 's2', name: 'anomaly.detect', durationMs: 450, status: 'OK' },
    { spanId: 's3', name: 'rwa.enrich', durationMs: 890, status: 'OK' },
    { spanId: 's4', name: 'audit.record', durationMs: 320, status: 'OK' },
    { spanId: 's5', name: 'safety.check', durationMs: 180, status: 'OK' },
    { spanId: 's6', name: 'intel.serve_x402', durationMs: 670, status: 'OK' },
  ]
}

function mockBlock() {
  return {
    block_height: getLiveBlockHeight(),
    block_hash: '0x' + Array.from({length:64}, ()=> Math.floor(Math.random()*16).toString(16)).join(''),
    era_id: 5280,
    timestamp: new Date().toISOString(),
    validator: '0x203cd…bace7',
    tx_count: 12,
    transfer_count: 8,
  }
}

// ─── Hybrid API object (matches current liveApi shape in App.jsx) ───

const hybridApi = {
  // Prices — already has good caching/fallback in liveApi
  fetchCSPRPrice: withFallback(fetchCSPRPrice, () => ({ usd: 0.0142, btc: 0.000000165, change_24h: -2.1, market_cap: 175_000_000, vol_24h: 3_200_000 })),
  fetchCSPRPriceHistory: withFallback(fetchCSPRPriceHistory, () => {
    const now = Date.now()
    return Array.from({ length: 7 }, (_, i) => ({
      ts: now - (6 - i) * 86_400_000,
      price: 0.012 + Math.random() * 0.004,
    }))
  }),
  fetchNetworkInfo: withFallback(fetchNetworkInfo, mockBlock),
  fetchAccountDeploys: withFallback(fetchAccountDeploys, () => {
    return Object.entries(CONTRACT_HASHES).map(([name, hash], i) => ({
      deploy_hash: hash,
      timestamp: new Date(Date.now() - i * 120_000).toISOString(),
      cost: '200000000000',
      status: 'executed',
      contract: name,
    }))
  }),

  // AI endpoints — real Groq with mock fallback
  riskQuery: withFallback(
    async (params) => {
      const result = await liveRiskQuery(params)
      return result
    },
    (params) => mockRiskResult(params.query)
  ),
  detectAnomaly: withFallback(
    async (metrics) => {
      const result = await liveDetectAnomaly(metrics)
      return result
    },
    mockAnomalyResult
  ),
  assessRWA: withFallback(
    async (asset) => {
      const result = await liveAssessRWA(asset)
      return result
    },
    mockRWAResult
  ),

  // Findings — already hybrid with seed fallback
  fetchLiveFindings: fetchLiveFindings,
  fetchFinding: fetchFinding,
  fetchRiskScore: fetchRiskScore,

  // Audit — try live, mock fallback
  getAuditLog: withFallback(
    async (limit) => {
      const r = await fetch(`${API_BASE}/chain/audit?limit=${limit || 10}`, {
        signal: AbortSignal.timeout(8000),
        headers: { Accept: 'application/json' },
      })
      if (r.ok) {
        const d = await r.json()
        return d?.entries ?? []
      }
      throw new Error('audit fetch failed')
    },
    mockAuditLog
  ),
  writeAudit: async (action, actor, details) => {
    try {
      const r = await fetch(`${API_BASE}/chain/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, actor, details }),
        signal: AbortSignal.timeout(10000),
      })
      if (r.ok) {
        const d = await r.json()
        return { ...d, _source: 'live' }
      }
    } catch {}
    // Mock fallback
    return {
      deploy_hash: `0x${Array.from({length:64}, ()=> Math.floor(Math.random()*16).toString(16)).join('')}_mock_${Date.now()}`,
      success: true,
      _source: 'fallback',
    }
  },

  // Health — already hybrid
  health: withFallback(liveHealth, () => ({
    status: 'ok', version: '4.0.0', mode: 'fallback', agents: 6, contracts: 8,
    groq_connected: false, cspr_price_usd: 0.0142, network: 'casper-test',
  })),

  // Spans — try live, mock fallback
  getSpans: withFallback(
    async () => {
      const r = await fetch(`${API_BASE}/agent/spans`, {
        signal: AbortSignal.timeout(8000),
        headers: { Accept: 'application/json' },
      })
      if (r.ok) {
        const d = await r.json()
        return d?.spans ?? []
      }
      throw new Error('spans fetch failed')
    },
    mockSpans
  ),

  // Static data — always the same
  deployHashes: CONTRACT_HASHES,
  deployerAccount: DEPLOYER_ACCOUNT,
  getBlockHeight: getLiveBlockHeight,
  seedFindings: SEED_FINDINGS,
}

export default hybridApi
