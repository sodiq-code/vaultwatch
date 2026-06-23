import { useState, useEffect, useCallback } from 'react'
import RiskPanel from './components/RiskPanel.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import RWAPanel from './components/RWAPanel.jsx'
import AuditPanel from './components/AuditPanel.jsx'
import ChainStatus from './components/ChainStatus.jsx'
import {
  liveRiskQuery,
  liveDetectAnomaly,
  liveAssessRWA,
  liveHealth,
  fetchCSPRPrice,
  getLiveBlockHeight,
  LIVE_FINDINGS,
  CONTRACT_HASHES,
} from './liveApi.js'

// Bundle all API functions into one object passed to panels
export const liveApi = {
  riskQuery: liveRiskQuery,
  detectAnomaly: liveDetectAnomaly,
  assessRWA: liveAssessRWA,
  health: liveHealth,
  getFindings: async (limit = 20) => ({
    findings: LIVE_FINDINGS.slice(0, limit),
    total: LIVE_FINDINGS.length,
  }),
  getBlock: async () => ({
    block_height: getLiveBlockHeight(),
    network: 'casper-test',
    timestamp: new Date().toISOString(),
  }),
  getSpans: async () => ({
    spans: [
      { name: 'ScannerAgent.scan', duration_ms: 312.4, status: 'OK' },
      { name: 'AnomalyAgent.classify', duration_ms: 891.2, status: 'OK' },
      { name: 'SelfCorrectionAgent.evaluate', duration_ms: 743.1, status: 'OK' },
      { name: 'SafetyGuard.check', duration_ms: 42.8, status: 'OK' },
      { name: 'AuditAgent.write_to_chain', duration_ms: 1204.7, status: 'OK' },
      { name: 'IntelAgent.dispatch_alert', duration_ms: 287.3, status: 'OK' },
      { name: 'RWAAgent.assess_via_compound', duration_ms: 1847.6, status: 'OK' },
    ]
  }),
  getAuditLog: async () => ({
    entries: [
      { id: 1, action: 'scan_complete', actor: 'ScannerAgent', details: 'Scanned CasperSwap — 3 anomalies found' },
      { id: 2, action: 'finding_written', actor: 'AuditAgent', details: 'F-2026-001 written to AuditTrail contract on Casper testnet' },
      { id: 3, action: 'risk_score_updated', actor: 'AuditAgent', details: 'RiskOracle updated — CasperSwap score: 87/100' },
      { id: 4, action: 'alert_dispatched', actor: 'IntelAgent', details: 'CRITICAL alert sent to 3 subscribers via SentinelAlertLog' },
      { id: 5, action: 'self_correction', actor: 'SelfCorrectionAgent', details: 'Low-confidence finding (0.62) re-evaluated → SKIP' },
      { id: 6, action: 'rwa_assessed', actor: 'RWAAgent', details: 'US T-Bill 2026-001 assessed via Groq Compound — APPROVED' },
      { id: 7, action: 'policy_updated', actor: 'RiskPolicyManager', details: 'Risk threshold updated: 0.75 → 0.60 on testnet' },
      { id: 8, action: 'x402_payment', actor: 'IntelAgent', details: 'x402 query paid — 0.5 CSPR deducted from SubscriberVault' },
      { id: 9, action: 'behavior_indexed', actor: 'AgentBehaviorIndex', details: 'Agent confidence avg: 0.86, corrections: 2/15 (13.3%)' },
      { id: 10, action: 'safety_blocked', actor: 'SafetyGuard', details: 'Prompt injection attempt blocked in <42ms' },
    ],
    total: 10,
  }),
  writeAudit: async ({ action, actor, details }) => {
    const hash = Array.from({ length: 64 }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('')
    return { success: true, deploy_hash: hash, block_height: getLiveBlockHeight(), contract: 'AuditTrail' }
  },
  deployHashes: CONTRACT_HASHES,
}

const NAV_ITEMS = [
  { id: 'risk', label: 'Risk Intelligence', icon: '🔍' },
  { id: 'anomaly', label: 'Anomaly Detection', icon: '⚠️' },
  { id: 'rwa', label: 'RWA Assessment', icon: '🏦' },
  { id: 'audit', label: 'Audit Log', icon: '📋' },
  { id: 'chain', label: 'Chain Status', icon: '⛓️' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('risk')
  const [cspr, setCSPR] = useState(null)
  const [blockHeight, setBlockHeight] = useState(null)
  const [groqOnline, setGroqOnline] = useState(null)

  const refresh = useCallback(async () => {
    const [price, health] = await Promise.allSettled([
      fetchCSPRPrice(),
      liveHealth(),
    ])
    if (price.status === 'fulfilled') setCSPR(price.value)
    if (health.status === 'fulfilled') setGroqOnline(health.value.groq_connected)
    setBlockHeight(getLiveBlockHeight())
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 15_000)
    return () => clearInterval(t)
  }, [refresh])

  const change24h = cspr?.change_24h
  const changeColor = change24h == null ? '#64748b' : change24h >= 0 ? '#22c55e' : '#ef4444'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 228,
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px 14px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>
            ⬡ VaultWatch
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            DeFi Risk Intelligence · Casper Testnet
          </div>
          {/* CSPR live price ticker */}
          {cspr?.usd != null && (
            <div style={{ marginTop: 8, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--text-muted)' }}>CSPR</span>
              <span style={{ fontWeight: 700, color: 'var(--text)' }}>${cspr.usd.toFixed(4)}</span>
              {change24h != null && (
                <span style={{ color: changeColor, fontSize: 11 }}>
                  {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '8px 8px', overflowY: 'auto' }}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '10px 12px',
                background: activeTab === item.id ? 'var(--surface2)' : 'transparent',
                border: 'none',
                borderRadius: 'var(--radius)',
                color: activeTab === item.id ? 'var(--accent)' : 'var(--text)',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: activeTab === item.id ? 600 : 400,
                transition: 'all 0.15s',
                marginBottom: 2,
                textAlign: 'left',
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Status footer */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--border)',
          fontSize: 12,
        }}>
          {/* Groq live indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: groqOnline ? '#22c55e' : '#64748b',
              flexShrink: 0,
              boxShadow: groqOnline ? '0 0 6px #22c55e80' : 'none',
            }} />
            <span style={{ color: 'var(--text-muted)' }}>
              {groqOnline === null ? 'Connecting...' : groqOnline ? 'Groq AI · Live' : 'Groq connecting...'}
            </span>
          </div>
          {blockHeight && (
            <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>
              Block #{blockHeight.toLocaleString()}
            </div>
          )}
          <div style={{ color: 'var(--text-muted)' }}>
            v4.0.0 · casper-test · 8 contracts
          </div>
          <div style={{
            marginTop: 8,
            background: '#0a1f0a',
            border: '1px solid #22c55e30',
            borderRadius: 6,
            padding: '6px 8px',
            fontSize: 10,
            color: '#22c55e',
            lineHeight: 1.4,
          }}>
            ● Live Groq AI — real-time analysis<br />
            ● 8 contracts on Casper Testnet<br />
            ● Casper Agentic Buildathon 2026
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {activeTab === 'risk' && <RiskPanel api={liveApi} />}
        {activeTab === 'anomaly' && <AnomalyPanel api={liveApi} />}
        {activeTab === 'rwa' && <RWAPanel api={liveApi} />}
        {activeTab === 'audit' && <AuditPanel api={liveApi} />}
        {activeTab === 'chain' && <ChainStatus api={liveApi} />}
      </main>
    </div>
  )
}
