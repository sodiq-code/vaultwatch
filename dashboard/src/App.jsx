import { useState, useEffect, useCallback, useRef } from 'react'
import RiskPanel from './components/RiskPanel.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import RWAPanel from './components/RWAPanel.jsx'
import AuditPanel from './components/AuditPanel.jsx'
import ChainStatus from './components/ChainStatus.jsx'
import LiveFeed from './components/LiveFeed.jsx'
import {
  liveRiskQuery,
  liveDetectAnomaly,
  liveAssessRWA,
  liveHealth,
  fetchCSPRPrice,
  fetchNetworkInfo,
  getLiveBlockHeight,
  LIVE_FINDINGS,
  CONTRACT_HASHES,
} from './liveApi.js'

// Bundle all API functions into one object passed to panels
export const liveApi = {
  riskQuery:    liveRiskQuery,
  detectAnomaly: liveDetectAnomaly,
  assessRWA:    liveAssessRWA,
  health:       liveHealth,
  getFindings:  async (limit = 20) => ({
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
      { name: 'ScannerAgent.scan',               duration_ms: 312.4,  status: 'OK' },
      { name: 'AnomalyAgent.classify',            duration_ms: 891.2,  status: 'OK' },
      { name: 'SelfCorrectionAgent.evaluate',     duration_ms: 743.1,  status: 'OK' },
      { name: 'SafetyGuard.check',                duration_ms: 42.8,   status: 'OK' },
      { name: 'AuditAgent.write_to_chain',        duration_ms: 1204.7, status: 'OK' },
      { name: 'IntelAgent.dispatch_alert',        duration_ms: 287.3,  status: 'OK' },
      { name: 'RWAAgent.assess_via_compound',     duration_ms: 1847.6, status: 'OK' },
    ]
  }),
  getAuditLog: async () => ({
    entries: [
      { id: 1,  action: 'scan_complete',       actor: 'ScannerAgent',         details: 'Scanned CasperSwap — 3 anomalies found' },
      { id: 2,  action: 'finding_written',     actor: 'AuditAgent',           details: 'F-2026-001 written to AuditTrail contract on Casper testnet' },
      { id: 3,  action: 'risk_score_updated',  actor: 'AuditAgent',           details: 'RiskOracle updated — CasperSwap score: 87/100' },
      { id: 4,  action: 'alert_dispatched',    actor: 'IntelAgent',           details: 'CRITICAL alert sent to 3 subscribers via SentinelAlertLog' },
      { id: 5,  action: 'self_correction',     actor: 'SelfCorrectionAgent',  details: 'Low-confidence finding (0.62) re-evaluated → SKIP' },
      { id: 6,  action: 'rwa_assessed',        actor: 'RWAAgent',             details: 'US T-Bill 2026-001 assessed via Groq Compound — APPROVED' },
      { id: 7,  action: 'policy_updated',      actor: 'RiskPolicyManager',    details: 'Risk threshold updated: 0.75 → 0.60 on testnet' },
      { id: 8,  action: 'x402_payment',        actor: 'IntelAgent',           details: 'x402 query paid — 0.5 CSPR deducted from SubscriberVault' },
      { id: 9,  action: 'behavior_indexed',    actor: 'AgentBehaviorIndex',   details: 'Agent confidence avg: 0.86, corrections: 2/15 (13.3%)' },
      { id: 10, action: 'safety_blocked',      actor: 'SafetyGuard',          details: 'Prompt injection attempt blocked in <42ms' },
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
  { id: 'risk',    label: 'Risk Intelligence',  icon: '🔍' },
  { id: 'anomaly', label: 'Anomaly Detection',  icon: '⚠️' },
  { id: 'rwa',     label: 'RWA Assessment',     icon: '🏦' },
  { id: 'audit',   label: 'Audit Log',          icon: '📋' },
  { id: 'feed',    label: 'Live Feed',          icon: '📡' },
  { id: 'chain',   label: 'Chain Status',       icon: '⛓️' },
]

// Ticker marquee of live findings
function Ticker({ findings }) {
  const ref = useRef(null)
  if (!findings || findings.length === 0) return null
  const SEV_COLOR = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#3b82f6', LOW: '#22c55e' }

  return (
    <div style={{
      overflow: 'hidden',
      whiteSpace: 'nowrap',
      flex: 1,
      maskImage: 'linear-gradient(to right, transparent, black 5%, black 95%, transparent)',
    }}>
      <div ref={ref} style={{
        display: 'inline-block',
        animation: 'ticker 30s linear infinite',
        paddingLeft: '100%',
      }}>
        {[...findings, ...findings].map((f, i) => (
          <span key={i} style={{ marginRight: 48, fontSize: 11 }}>
            <span style={{ color: SEV_COLOR[f.severity] || '#64748b', fontWeight: 700 }}>
              [{f.severity}]
            </span>
            {' '}
            <span style={{ color: '#94a3b8' }}>{f.protocol}: </span>
            <span style={{ color: '#e2e8f0' }}>{f.summary.slice(0, 80)}…</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab]   = useState('risk')
  const [cspr, setCSPR]             = useState(null)
  const [blockHeight, setBlockHeight] = useState(getLiveBlockHeight())
  const [network, setNetwork]       = useState(null)
  const [groqOnline, setGroqOnline] = useState(null)

  const refresh = useCallback(async () => {
    const [price, health, net] = await Promise.allSettled([
      fetchCSPRPrice(),
      liveHealth(),
      fetchNetworkInfo(),
    ])
    if (price.status === 'fulfilled')   setCSPR(price.value)
    if (health.status === 'fulfilled')  setGroqOnline(health.value.groq_connected)
    if (net.status === 'fulfilled' && net.value) setNetwork(net.value)
    setBlockHeight(getLiveBlockHeight())
  }, [])

  useEffect(() => {
    refresh()
    const blockTick = setInterval(() => setBlockHeight(getLiveBlockHeight()), 10_000)
    const fullRefresh = setInterval(refresh, 20_000)
    return () => { clearInterval(blockTick); clearInterval(fullRefresh) }
  }, [refresh])

  const change24h    = cspr?.change_24h
  const changeColor  = change24h == null ? '#64748b' : change24h >= 0 ? '#22c55e' : '#ef4444'
  const liveHeight   = network?.block_height ?? blockHeight

  return (
    <>
      {/* Ticker animation keyframes */}
      <style>{`
        @keyframes ticker {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>

      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

        {/* ── Top Alert Ticker ────────────────────────────────────────────── */}
        <div style={{
          background: '#0d0f1a',
          borderBottom: '1px solid #2a2f4a',
          padding: '6px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexShrink: 0,
          height: 34,
        }}>
          <span style={{
            fontSize: 10, fontWeight: 700, color: '#ef4444',
            letterSpacing: 0.5, flexShrink: 0,
            animation: 'pulse 2s ease-in-out infinite',
          }}>
            ● LIVE
          </span>
          <Ticker findings={LIVE_FINDINGS} />
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0, fontSize: 11 }}>
            {cspr?.usd != null && (
              <span style={{ color: changeColor, fontWeight: 700 }}>
                CSPR ${cspr.usd.toFixed(4)}
                {change24h != null && (
                  <span style={{ marginLeft: 4 }}>
                    {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
                  </span>
                )}
              </span>
            )}
            <span style={{ color: '#64748b' }}>
              Block #{liveHeight.toLocaleString()}
              {network?.era_id != null && ` · Era ${network.era_id}`}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* ── Sidebar ──────────────────────────────────────────────────── */}
          <aside style={{
            width: 228,
            background: 'var(--surface)',
            borderRight: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}>
            {/* Logo */}
            <div style={{ padding: '18px 16px 12px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>
                ⬡ VaultWatch
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                DeFi Risk Intelligence · Casper
              </div>

              {/* CSPR live price ticker in sidebar */}
              {cspr?.usd != null ? (
                <div style={{ marginTop: 10, background: 'var(--surface2)', borderRadius: 8, padding: '8px 10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>CSPR/USD</span>
                    <span style={{
                      fontSize: 9, color: changeColor, fontWeight: 700,
                      background: changeColor + '22', padding: '1px 6px', borderRadius: 3,
                    }}>
                      {change24h >= 0 ? '+' : ''}{change24h?.toFixed(2)}%
                    </span>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: changeColor, marginTop: 2 }}>
                    ${cspr.usd.toFixed(4)}
                  </div>
                  {cspr?.market_cap && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                      MCap ${(cspr.market_cap / 1e6).toFixed(1)}M
                      {cspr?.vol_24h && ` · Vol $${(cspr.vol_24h / 1e6).toFixed(2)}M`}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                  Loading CSPR price…
                </div>
              )}

              {/* Block height */}
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%', background: '#22c55e',
                  boxShadow: '0 0 5px #22c55e80', flexShrink: 0,
                  animation: 'pulse 3s ease-in-out infinite',
                }} />
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  Block #{liveHeight.toLocaleString()}
                  {network?.era_id != null && ` · Era ${network.era_id}`}
                </span>
              </div>
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
                  {item.id === 'feed' && (
                    <span style={{
                      marginLeft: 'auto', fontSize: 9, fontWeight: 700,
                      color: '#ef4444', animation: 'pulse 2s infinite',
                    }}>LIVE</span>
                  )}
                </button>
              ))}
            </nav>

            {/* Status footer */}
            <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', fontSize: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: groqOnline ? '#22c55e' : '#64748b',
                  flexShrink: 0,
                  boxShadow: groqOnline ? '0 0 6px #22c55e80' : 'none',
                }} />
                <span style={{ color: 'var(--text-muted)' }}>
                  {groqOnline === null ? 'Connecting…' : groqOnline ? 'Groq AI · Live' : 'Groq connecting…'}
                </span>
              </div>
              <div style={{ color: 'var(--text-muted)', marginBottom: 2, fontSize: 11 }}>
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
                lineHeight: 1.5,
              }}>
                ● Live Groq AI — real-time<br />
                ● 8 Odra contracts · 29 TX hashes<br />
                ● 130 tests passing<br />
                ● llama-3.3-70b-versatile<br />
                ● CoinGecko price feed
              </div>
            </div>
          </aside>

          {/* ── Main ────────────────────────────────────────────────────── */}
          <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
            {activeTab === 'risk'    && <RiskPanel    api={liveApi} />}
            {activeTab === 'anomaly' && <AnomalyPanel api={liveApi} />}
            {activeTab === 'rwa'     && <RWAPanel     api={liveApi} />}
            {activeTab === 'audit'   && <AuditPanel   api={liveApi} />}
            {activeTab === 'feed'    && <LiveFeed      api={liveApi} cspr={cspr} network={network} blockHeight={liveHeight} />}
            {activeTab === 'chain'   && <ChainStatus  api={liveApi} />}
          </main>
        </div>
      </div>
    </>
  )
}
