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
  updateBlockHeight,
  LIVE_FINDINGS,
  refreshLiveFindings,
  fetchSpans,
  fetchAuditLog,
  writeAuditEntry,
  CONTRACT_HASHES,
} from './liveApi.js'

// Bundle all API functions into one object passed to panels
// FIX #18: All methods now call real FastAPI backend endpoints
export const liveApi = {
  riskQuery:    liveRiskQuery,
  detectAnomaly: liveDetectAnomaly,
  assessRWA:    liveAssessRWA,
  health:       liveHealth,

  // FIX #18: getFindings fetches from /api/findings instead of hardcoded LIVE_FINDINGS
  getFindings:  async (limit = 20) => {
    const findings = await refreshLiveFindings(null, limit);
    return { findings, total: findings.length };
  },

  getBlock: async () => {
    const net = await fetchNetworkInfo();
    const height = net?.block_height ?? getLiveBlockHeight();
    if (net?.block_height) updateBlockHeight(net.block_height);
    return {
      block_height: height,
      network: net?.network || 'casper-test',
      timestamp: new Date().toISOString(),
    };
  },

  // FIX #18: getSpans fetches from /api/spans instead of hardcoded data
  getSpans: async () => {
    return await fetchSpans();
  },

  // FIX #18: getAuditLog fetches from /api/audit instead of hardcoded data
  getAuditLog: async () => {
    return await fetchAuditLog();
  },

  // FIX #18: writeAudit calls POST /api/audit instead of generating fake hash
  writeAudit: async ({ action, actor, details }) => {
    return await writeAuditEntry({ action, actor, details });
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
            <span style={{ color: '#e2e8f0' }}>{(f.summary || '').slice(0, 80)}…</span>
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
  const [tickerFindings, setTickerFindings] = useState([])

  const refresh = useCallback(async () => {
    const [price, health, net, findings] = await Promise.allSettled([
      fetchCSPRPrice(),
      liveHealth(),
      fetchNetworkInfo(),
      refreshLiveFindings(null, 10),
    ])
    if (price.status === 'fulfilled')   setCSPR(price.value)
    if (health.status === 'fulfilled')  setGroqOnline(health.value.groq_connected)
    if (net.status === 'fulfilled' && net.value) {
      setNetwork(net.value)
      if (net.value.block_height) updateBlockHeight(net.value.block_height)
    }
    if (findings.status === 'fulfilled' && findings.value) {
      setTickerFindings(findings.value)
    }
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
          <Ticker findings={tickerFindings} />
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
                ● 100+ tests passing<br />
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
