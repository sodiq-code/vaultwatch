/**
 * VaultWatch App.jsx — Premium dashboard shell with sidebar navigation,
 * ticker, panel routing, and CSPR.click integration.
 */
import { useState, useEffect } from 'react'
import { CSPRClickProvider } from './csprclick.js'
import { useToast } from './hooks/useToast.js'
import { useResponsive } from './hooks/useResponsive.js'
import { ToastContainer } from './ui/ToastContainer.jsx'
import hybridApi from './api/hybridApi.js'
import { CONTRACT_HASHES } from './liveApi.js'

import { WalletBar } from './components/WalletBar.jsx'
import { AgentPipelinePanel } from './components/AgentPipelinePanel.jsx'
import { RiskPanel } from './components/RiskPanel.jsx'
import { AnomalyPanel } from './components/AnomalyPanel.jsx'
import { RWAAssetsPanel } from './components/RWAAssetsPanel.jsx'
import { AttestationsPanel } from './components/AttestationsPanel.jsx'
import { LiveFeed } from './components/LiveFeed.jsx'
import { X402PaymentsPanel } from './components/X402PaymentsPanel.jsx'
import { ChainStatus } from './components/ChainStatus.jsx'

import { GlassCard } from './ui/GlassCard.jsx'
import { Badge, SourceBadge, HexBadge } from './ui/Badge.jsx'
import { StatCard } from './ui/StatCard.jsx'
import { AnimatedCounter } from './ui/AnimatedCounter.jsx'

// ─── Navigation items ───
const NAV_ITEMS = [
  { id: 'pipeline',    label: 'Agent Pipeline',    icon: '⚡', hex: '1' },
  { id: 'risk',        label: 'Risk Intelligence',  icon: '🛡️', hex: '2' },
  { id: 'anomaly',     label: 'Anomaly Detection',  icon: '🔍', hex: '3' },
  { id: 'rwa',         label: 'RWA Assets',         icon: '📊', hex: '4' },
  { id: 'attestations', label: 'Attestations',      icon: '📋', hex: '5' },
  { id: 'events',      label: 'Agent Events',       icon: '📡', hex: '6' },
  { id: 'x402',        label: 'x402 Payments',      icon: '💰', hex: '7' },
  { id: 'chain',       label: 'Chain Status',       icon: '🔗', hex: '8' },
]

const PANEL_MAP = {
  pipeline:    AgentPipelinePanel,
  risk:        RiskPanel,
  anomaly:     AnomalyPanel,
  rwa:         RWAAssetsPanel,
  attestations: AttestationsPanel,
  events:      LiveFeed,
  x402:        X402PaymentsPanel,
  chain:       ChainStatus,
}

const TICKER_ITEMS = [
  '⚡ ScannerAgent: 342 runs, 28 findings',
  '🛡️ RiskOracle: CRITICAL whale concentration alert',
  '🔍 AnomalyAgent: 12 anomalies detected',
  '📊 RWAAgent: Bond yield 4.25%, Gold $2350',
  '📋 AuditTrail: 5 on-chain attestations verified',
  '🧠 IntelAgent: x402 payment flow active',
  '🔗 Casper Testnet: Block height syncing',
]

// ─── App Shell ───
function AppShell() {
  const { toasts, addToast, removeToast } = useToast()
  const { isMobile, sidebarOpen, toggleSidebar, closeSidebar } = useResponsive()
  const [activePanel, setActivePanel] = useState('pipeline')
  const [price, setPrice] = useState(null)
  const [blockHeight, setBlockHeight] = useState(0)
  const [health, setHealth] = useState(null)

  // Load sidebar data
  useEffect(() => {
    const loadSidebarData = async () => {
      try {
        const priceData = await hybridApi.fetchCSPRPrice()
        if (priceData) setPrice(priceData)
      } catch {}
      try {
        const netData = await hybridApi.fetchNetworkInfo()
        if (netData) setBlockHeight(netData.block_height)
      } catch {}
      try {
        const h = await hybridApi.health()
        if (h) setHealth(h)
      } catch {}
    }
    loadSidebarData()
    const interval = setInterval(loadSidebarData, 15000)
    return () => clearInterval(interval)
  }, [])

  // Auto-refresh block height
  useEffect(() => {
    const bhInterval = setInterval(() => {
      setBlockHeight(hybridApi.getBlockHeight())
    }, 5000)
    return () => clearInterval(bhInterval)
  }, [])

  // Close sidebar on panel change (mobile)
  const handlePanelChange = (id) => {
    setActivePanel(id)
    if (isMobile) closeSidebar()
  }

  const PanelComponent = PANEL_MAP[activePanel] || ChainStatus

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg)',
    }}>
      {/* Top bar — WalletBar */}
      <WalletBar />

      {/* Ticker marquee */}
      <div style={{
        overflow: 'hidden',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '6px 0',
        position: 'relative',
      }}>
        <div style={{
          display: 'flex',
          gap: 'var(--space-xl)',
          animation: 'ticker 30s linear infinite',
          whiteSpace: 'nowrap',
        }}>
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span key={i} style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-muted)',
              fontWeight: 'var(--font-weight-medium)',
            }}>
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* Main layout — sidebar + content */}
      <div style={{
        display: 'flex',
        flex: 1,
        overflow: 'hidden',
      }}>
        {/* Mobile hamburger */}
        {isMobile && !sidebarOpen && (
          <button
            onClick={toggleSidebar}
            style={{
              position: 'fixed',
              top: 'var(--space-md)',
              left: 'var(--space-md)',
              zIndex: 'var(--z-overlay)',
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
              color: 'var(--accent)',
              fontSize: 'var(--font-size-lg)',
              cursor: 'pointer',
              boxShadow: 'var(--shadow-glow)',
            }}
          >
            ☰
          </button>
        )}

        {/* Sidebar */}
        <aside style={{
          width: isMobile ? (sidebarOpen ? 260 : 0) : 240,
          minWidth: isMobile ? 0 : 240,
          background: 'var(--bg-elevated)',
          borderRight: '1px solid var(--border)',
          overflowY: 'auto',
          overflowX: 'hidden',
          transition: 'width var(--transition-normal)',
          display: 'flex',
          flexDirection: 'column',
          position: isMobile ? 'fixed' : 'relative',
          top: isMobile ? 0 : 'auto',
          left: isMobile ? 0 : 'auto',
          height: isMobile ? '100vh' : 'auto',
          zIndex: isMobile ? 'var(--z-sidebar)' : 'auto',
          ...(isMobile && sidebarOpen ? { boxShadow: 'var(--shadow-xl)' } : {}),
        }}>
          {/* Logo section */}
          <div style={{
            padding: 'var(--space-lg)',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
          }}>
            <div className="hex-badge" style={{ width: 36, height: 36, fontSize: 16, animation: 'hexPulse 3s ease-in-out infinite' }}>V</div>
            <div>
              <div style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--text)',
                letterSpacing: '-0.5px',
              }}>
                VaultWatch
              </div>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                DeFi Risk Intelligence
              </div>
            </div>
          </div>

          {/* CSPR price card */}
          <div style={{ padding: 'var(--space-md)' }}>
            <GlassCard hover={false} style={{
              padding: 'var(--space-md)',
              background: 'rgba(0, 212, 255, 0.06)',
            }}>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontWeight: 'var(--font-weight-medium)',
              }}>
                CSPR/USD
              </div>
              <div style={{
                fontSize: 'var(--font-size-xl)',
                fontWeight: 'var(--font-weight-bold)',
                color: price?.change_24h > 0 ? 'var(--success)' : price?.change_24h < 0 ? 'var(--danger)' : 'var(--accent)',
                lineHeight: 1.2,
              }}>
                ${price?.usd?.toFixed(4) || '—'}
              </div>
              {price?.change_24h !== null && price?.change_24h !== undefined && (
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: price.change_24h > 0 ? 'var(--success)' : 'var(--danger)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {price.change_24h > 0 ? '↑' : '↓'} {Math.abs(price.change_24h).toFixed(2)}%
                </div>
              )}
              <SourceBadge source={price?._source || 'live'} style={{ marginTop: 4 }} />
            </GlassCard>
          </div>

          {/* Block height */}
          <div style={{ padding: '0 var(--space-md)' }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 'var(--font-size-xs)',
              padding: '6px 10px',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-sm)',
            }}>
              <span style={{ color: 'var(--text-muted)' }}>Block</span>
              <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                <AnimatedCounter value={blockHeight} formatter={(v) => Math.round(v).toLocaleString()} />
              </span>
            </div>
          </div>

          {/* Nav items */}
          <div style={{
            padding: 'var(--space-md)',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}>
            {NAV_ITEMS.map(item => {
              const isActive = activePanel === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => handlePanelChange(item.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    padding: '8px 12px',
                    background: isActive ? 'rgba(0, 212, 255, 0.12)' : 'transparent',
                    border: isActive ? '1px solid var(--border2)' : '1px solid transparent',
                    borderRadius: 'var(--radius-md)',
                    color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                    fontSize: 'var(--font-size-sm)',
                    fontWeight: isActive ? 'var(--font-weight-semibold)' : 'var(--font-weight-normal)',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                    textAlign: 'left',
                    ...(isActive ? { boxShadow: 'var(--shadow-glow)' } : {}),
                  }}
                >
                  <span className="hex-badge" style={{
                    width: 24,
                    height: 24,
                    fontSize: 10,
                    background: isActive ? 'var(--gradient-accent)' : 'rgba(107, 127, 160, 0.3)',
                    transition: 'background var(--transition-fast)',
                  }}>
                    {item.hex}
                  </span>
                  <span style={{ fontSize: '14px' }}>{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              )
            })}
          </div>

          {/* Footer — Groq status */}
          <div style={{
            padding: 'var(--space-md)',
            borderTop: '1px solid var(--border)',
          }}>
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-dark)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: health?.groq_connected ? 'var(--success)' : 'var(--warning)',
                animation: health?.groq_connected ? 'glowPulseGreen 2s ease-in-out infinite' : 'pulse 2s ease-in-out infinite',
              }} />
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                Groq: {health?.groq_connected ? 'Connected' : 'Fallback Mode'}
              </span>
            </div>
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-dark)',
              fontFamily: 'var(--font-mono)',
              marginTop: 2,
            }}>
              v{health?.version || '5.0.0'} • {health?.mode || 'hybrid'}
            </div>
          </div>
        </aside>

        {/* Mobile overlay when sidebar open */}
        {isMobile && sidebarOpen && (
          <div
            onClick={closeSidebar}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0, 0, 0, 0.5)',
              zIndex: 'var(--z-overlay)',
            }}
          />
        )}

        {/* Main content area */}
        <main style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          minHeight: 0,
        }}>
          <PanelComponent api={hybridApi} addToast={addToast} />
        </main>
      </div>

      {/* Toast container */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  )
}

// ─── Root App with CSPRClickProvider ───
export default function App() {
  return (
    <CSPRClickProvider>
      <AppShell />
    </CSPRClickProvider>
  )
}
