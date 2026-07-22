import { useState, useEffect, useCallback } from 'react'
import { CSPRClickProvider } from './csprclick.js'
import WalletBar from './components/WalletBar.jsx'
import RiskPanel from './components/RiskPanel.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import RWAPanel from './components/RWAPanel.jsx'
import AuditPanel from './components/AuditPanel.jsx'
import ChainStatus from './components/ChainStatus.jsx'
import LiveFeed from './components/LiveFeed.jsx'
import hybridApi from './api/hybridApi.js'
import { useToast } from './hooks/useToast.js'
import { useResponsive } from './hooks/useResponsive.js'
import { ToastContainer } from './ui/ToastContainer.jsx'
import { Badge } from './ui/Badge.jsx'
import './animations.css'

/* ─── Navigation items (preserved from original) ─── */
const NAV_ITEMS = [
  { id: 'risk',    label: 'Risk Intelligence',  icon: '🔍' },
  { id: 'anomaly', label: 'Anomaly Detection',  icon: '⚠️' },
  { id: 'rwa',     label: 'RWA Assessment',     icon: '🏦' },
  { id: 'audit',   label: 'Audit Log',          icon: '📋' },
  { id: 'feed',    label: 'Live Feed',          icon: '📡' },
  { id: 'chain',   label: 'Chain Status',       icon: '⛓️' },
]

/* ─── Ticker marquee of live findings ─── */
function Ticker({ findings }) {
  if (!findings || findings.length === 0) return null
  const SEV_COLOR = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#3b82f6', LOW: '#22c55e' }

  return (
    <div style={{
      overflow: 'hidden',
      whiteSpace: 'nowrap',
      flex: 1,
      maskImage: 'linear-gradient(to right, transparent, black 5%, black 95%, transparent)',
    }}>
      <div style={{
        display: 'inline-block',
        animation: 'ticker 30s linear infinite',
        paddingLeft: '100%',
      }}>
        {[...findings, ...findings].map((f, i) => (
          <span key={i} style={{ marginRight: 48, fontSize: 'var(--font-size-xs)' }}>
            <span style={{ color: SEV_COLOR[f.severity] || 'var(--text-muted)', fontWeight: 700 }}>
              [{f.severity}]
            </span>
            {' '}
            <span style={{ color: 'var(--text-muted)' }}>{f.protocol}: </span>
            <span style={{ color: 'var(--text)' }}>{f.summary.slice(0, 80)}…</span>
          </span>
        ))}
      </div>
    </div>
  )
}

/* ─── Sidebar component — reused for both desktop and mobile ─── */
function SidebarContent({ activeTab, setActiveTab, cspr, change24h, changeColor, liveHeight, network, groqOnline, isMobile, closeSidebar }) {
  const navClick = useCallback((id) => {
    setActiveTab(id)
    if (isMobile) closeSidebar()
  }, [setActiveTab, isMobile, closeSidebar])

  return (
    <>
      {/* ── Logo + gradient header ── */}
      <div style={{
        padding: 'var(--space-lg)',
        background: 'var(--gradient-accent)',
        borderBottom: '1px solid var(--glass-border)',
        position: 'relative',
      }}>
        {/* Glass overlay on gradient */}
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(8px)',
        }} />
        <div style={{ position: 'relative' }}>
          <div style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-extrabold)',
            color: 'var(--text)',
            letterSpacing: '-0.5px',
          }}>
            ⬡ VaultWatch
          </div>
          <div style={{
            fontSize: 'var(--font-size-xs)',
            color: 'var(--text-muted)',
            marginTop: 'var(--space-xs)',
            letterSpacing: '0.5px',
          }}>
            DeFi Risk Intelligence · Casper
          </div>
        </div>
      </div>

      {/* ── CSPR Price glass card ── */}
      {cspr?.usd != null ? (
        <div
          className="glass-card-static"
          style={{
            margin: 'var(--space-md) var(--space-md) 0',
            padding: 'var(--space-md)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              fontWeight: 'var(--font-weight-semibold)',
            }}>CSPR/USD</span>
            {change24h != null && (
              <Badge
                variant={change24h >= 0 ? 'success' : 'danger'}
                size="sm"
                pulse={Math.abs(change24h) > 5}
              >
                {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
              </Badge>
            )}
          </div>
          <div style={{
            fontSize: 'var(--font-size-2xl)',
            fontWeight: 'var(--font-weight-extrabold)',
            color: changeColor,
            marginTop: 'var(--space-xs)',
            lineHeight: 1.2,
          }}>
            ${cspr.usd.toFixed(4)}
          </div>
          {cspr?.market_cap && (
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-muted)',
              marginTop: 'var(--space-xs)',
            }}>
              MCap ${(cspr.market_cap / 1e6).toFixed(1)}M
              {cspr?.vol_24h && ` · Vol $${(cspr.vol_24h / 1e6).toFixed(2)}M`}
            </div>
          )}
        </div>
      ) : (
        <div style={{
          margin: 'var(--space-md)',
          fontSize: 'var(--font-size-sm)',
          color: 'var(--text-muted)',
        }}>
          Loading CSPR price…
        </div>
      )}

      {/* ── Block height glass card ── */}
      <div
        className="glass-card-static"
        style={{
          margin: 'var(--space-sm) var(--space-md) var(--space-md)',
          padding: 'var(--space-sm) var(--space-md)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: 'var(--success)',
            boxShadow: '0 0 6px rgba(34, 197, 94, 0.5)',
            flexShrink: 0,
            animation: 'pulse 3s ease-in-out infinite',
          }} />
          <span style={{
            fontSize: 'var(--font-size-xs)',
            color: 'var(--text-muted)',
          }}>
            Block #{liveHeight.toLocaleString()}
            {network?.era_id != null && ` · Era ${network.era_id}`}
          </span>
        </div>
      </div>

      {/* ── Nav items with hover glow ── */}
      <nav style={{
        flex: 1,
        padding: 'var(--space-sm) var(--space-sm)',
        overflowY: 'auto',
      }}>
        {NAV_ITEMS.map(item => {
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              onClick={() => navClick(item.id)}
              className={isActive ? 'glass-card-static' : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                width: '100%',
                padding: '10px 12px',
                background: isActive ? 'var(--surface2)' : 'transparent',
                border: isActive ? '1px solid var(--glass-border-hover)' : '1px solid transparent',
                borderRadius: 'var(--radius-md)',
                color: isActive ? 'var(--accent)' : 'var(--text)',
                cursor: 'pointer',
                fontSize: 'var(--font-size-sm)',
                fontWeight: isActive ? 'var(--font-weight-semibold)' : 'var(--font-weight-normal)',
                transition: 'var(--transition-normal)',
                marginBottom: 2,
                textAlign: 'left',
                boxShadow: isActive ? 'var(--shadow-glow)' : 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'var(--surface2)'
                  e.currentTarget.style.boxShadow = 'var(--shadow-glow)'
                  e.currentTarget.style.border = '1px solid var(--glass-border-hover)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.border = '1px solid transparent'
                }
              }}
            >
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              <span>{item.label}</span>
              {item.id === 'feed' && (
                <Badge pulse size="sm" variant="danger" style={{ marginLeft: 'auto' }}>LIVE</Badge>
              )}
            </button>
          )
        })}
      </nav>

      {/* ── Sidebar footer: Groq status + version info ── */}
      <div style={{
        padding: 'var(--space-md)',
        borderTop: '1px solid var(--glass-border)',
        fontSize: 'var(--font-size-sm)',
      }}>
        {/* Groq status dot with glowPulse */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: groqOnline ? 'var(--success)' : 'var(--text-muted)',
            flexShrink: 0,
            animation: groqOnline ? 'glowPulseGreen 2s ease-in-out infinite' : 'pulse 2s ease-in-out infinite',
          }} />
          <span style={{ color: 'var(--text-muted)' }}>
            {groqOnline === null ? 'Connecting…' : groqOnline ? 'Groq AI · Live' : 'Groq connecting…'}
          </span>
        </div>
        <div style={{
          color: 'var(--text-muted)',
          marginBottom: 'var(--space-sm)',
          fontSize: 'var(--font-size-xs)',
        }}>
          v4.0.0 · casper-test · 8 contracts
        </div>
        <div
          className="glass-card-static"
          style={{
            padding: 'var(--space-sm) var(--space-md)',
            fontSize: 'var(--font-size-xs)',
            color: 'var(--success)',
            lineHeight: 1.5,
          }}
        >
          ● Live Groq AI — real-time<br />
          ● 8 Odra contracts · 29 TX hashes<br />
          ● 100+ tests passing<br />
          ● llama-3.3-70b-versatile<br />
          ● CoinGecko price feed
        </div>
      </div>
    </>
  )
}

/* ─── Main App ─── */
export default function App() {
  const [activeTab, setActiveTab]         = useState('risk')
  const [cspr, setCSPR]                   = useState(null)
  const [blockHeight, setBlockHeight]     = useState(hybridApi.getBlockHeight())
  const [network, setNetwork]             = useState(null)
  const [groqOnline, setGroqOnline]       = useState(null)
  const [liveFindings, setLiveFindings]   = useState(hybridApi.seedFindings)
  const [tabKey, setTabKey]               = useState(0)   // for fadeIn re-trigger on tab switch

  const { isMobile, sidebarOpen, toggleSidebar, closeSidebar, openSidebar } = useResponsive()
  const { toasts, addToast, removeToast }                  = useToast()

  const refresh = useCallback(async () => {
    const [price, health, net, findings] = await Promise.allSettled([
      hybridApi.fetchCSPRPrice(),
      hybridApi.health(),
      hybridApi.fetchNetworkInfo(),
      hybridApi.fetchLiveFindings(20),
    ])
    if (price.status === 'fulfilled' && price.value)   setCSPR(price.value)
    if (health.status === 'fulfilled' && health.value)  setGroqOnline(health.value.groq_connected ?? health.value.groq)
    if (net.status === 'fulfilled' && net.value)        setNetwork(net.value)
    if (findings.status === 'fulfilled' && findings.value?.findings?.length) {
      setLiveFindings(findings.value.findings)
    }
    setBlockHeight(hybridApi.getBlockHeight())
  }, [])

  useEffect(() => {
    refresh()
    const blockTick = setInterval(() => setBlockHeight(hybridApi.getBlockHeight()), 10_000)
    const fullRefresh = setInterval(refresh, 20_000)
    return () => { clearInterval(blockTick); clearInterval(fullRefresh) }
  }, [refresh])

  const handleTabChange = useCallback((id) => {
    setActiveTab(id)
    setTabKey(prev => prev + 1)  // re-trigger fadeIn animation
  }, [])

  const change24h    = cspr?.change_24h
  const changeColor  = change24h == null ? 'var(--text-muted)' : change24h >= 0 ? 'var(--success)' : 'var(--danger)'
  const liveHeight   = network?.block_height ?? blockHeight

  const panelProps = { api: hybridApi, addToast }

  return (
    <CSPRClickProvider>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg)',
        backgroundImage: 'var(--gradient-bg)',
      }}>

        {/* ── Wallet Bar ── */}
        <WalletBar />

        {/* ── Top Alert Ticker ── */}
        <div
          className="glass-card-static"
          style={{
            borderBottom: '1px solid var(--glass-border)',
            padding: '6px var(--space-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-md)',
            flexShrink: 0,
            height: 34,
            borderRadius: 0,
          }}
        >
          <Badge pulse variant="danger" size="sm">LIVE</Badge>
          <Ticker findings={liveFindings} />
          <div style={{
            display: 'flex',
            gap: 'var(--space-lg)',
            alignItems: 'center',
            flexShrink: 0,
            fontSize: 'var(--font-size-xs)',
          }}>
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
            <span style={{ color: 'var(--text-muted)' }}>
              Block #{liveHeight.toLocaleString()}
              {network?.era_id != null && ` · Era ${network.era_id}`}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* ── Mobile hamburger button ── */}
          {isMobile && (
            <button
              onClick={toggleSidebar}
              style={{
                position: 'fixed',
                top: 48,
                left: 'var(--space-md)',
                zIndex: 'var(--z-sidebar)',
                background: 'var(--glass-bg)',
                backdropFilter: 'blur(var(--glass-blur))',
                border: '1px solid var(--glass-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '8px 10px',
                color: 'var(--text)',
                fontSize: 'var(--font-size-lg)',
                cursor: 'pointer',
                boxShadow: 'var(--shadow-md)',
                transition: 'var(--transition-normal)',
              }}
              aria-label="Toggle sidebar"
            >
              ☰
            </button>
          )}

          {/* ── Mobile overlay backdrop ── */}
          {isMobile && sidebarOpen && (
            <div
              onClick={closeSidebar}
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.5)',
                backdropFilter: 'blur(4px)',
                zIndex: 'var(--z-overlay)',
                animation: 'fadeIn 0.2s ease-out',
              }}
            />
          )}

          {/* ── Sidebar ── */}
          <aside
            className="glass-card-static"
            style={{
              width: 228,
              background: 'var(--surface)',
              backdropFilter: 'blur(var(--glass-blur)) saturate(var(--glass-saturate))',
              borderRight: '1px solid var(--glass-border)',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              borderRadius: 0,
              boxShadow: 'var(--shadow-lg)',
              ...(isMobile ? {
                position: 'fixed',
                top: 0,
                left: 0,
                bottom: 0,
                zIndex: 'var(--z-sidebar)',
                transform: sidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
                transition: 'transform var(--transition-normal)',
                animation: sidebarOpen ? 'slideInLeft 0.25s ease-out' : undefined,
              } : {}),
            }}
          >
            {/* Close button for mobile */}
            {isMobile && sidebarOpen && (
              <button
                onClick={closeSidebar}
                style={{
                  position: 'absolute',
                  top: 'var(--space-sm)',
                  right: 'var(--space-sm)',
                  background: 'var(--surface2)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '4px 8px',
                  color: 'var(--text-muted)',
                  fontSize: 'var(--font-size-lg)',
                  cursor: 'pointer',
                  zIndex: 1,
                }}
                aria-label="Close sidebar"
              >
                ✕
              </button>
            )}

            <SidebarContent
              activeTab={activeTab}
              setActiveTab={handleTabChange}
              cspr={cspr}
              change24h={change24h}
              changeColor={changeColor}
              liveHeight={liveHeight}
              network={network}
              groqOnline={groqOnline}
              isMobile={isMobile}
              closeSidebar={closeSidebar}
            />
          </aside>

          {/* ── Main Content with fadeIn on tab switch ── */}
          <main
            key={tabKey}
            className="fade-in"
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: isMobile ? 'var(--space-md)' : 'var(--space-lg)',
              marginLeft: isMobile ? 0 : undefined,
            }}
          >
            {activeTab === 'risk'    && <RiskPanel    {...panelProps} />}
            {activeTab === 'anomaly' && <AnomalyPanel {...panelProps} />}
            {activeTab === 'rwa'     && <RWAPanel     {...panelProps} />}
            {activeTab === 'audit'   && <AuditPanel   {...panelProps} />}
            {activeTab === 'feed'    && <LiveFeed      api={hybridApi} addToast={addToast} cspr={cspr} network={network} blockHeight={liveHeight} />}
            {activeTab === 'chain'   && <ChainStatus  {...panelProps} />}
          </main>
        </div>
      </div>

      {/* ── Toast container at app root ── */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </CSPRClickProvider>
  )
}
