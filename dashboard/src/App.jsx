import { useState, useEffect, useCallback } from 'react'
import RiskPanel from './components/RiskPanel.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import RWAPanel from './components/RWAPanel.jsx'
import AuditPanel from './components/AuditPanel.jsx'
import ChainStatus from './components/ChainStatus.jsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const NAV_ITEMS = [
  { id: 'risk', label: 'Risk Intelligence', icon: '🔍' },
  { id: 'anomaly', label: 'Anomaly Detection', icon: '⚠️' },
  { id: 'rwa', label: 'RWA Assessment', icon: '🏦' },
  { id: 'audit', label: 'Audit Log', icon: '📋' },
  { id: 'chain', label: 'Chain Status', icon: '⛓️' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('risk')
  const [apiHealth, setApiHealth] = useState(null)
  const [blockHeight, setBlockHeight] = useState(null)

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/health`)
      const data = await r.json()
      setApiHealth(data.status === 'ok' ? 'online' : 'degraded')
    } catch {
      setApiHealth('offline')
    }
  }, [])

  const fetchBlockHeight = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/chain/block`)
      const data = await r.json()
      setBlockHeight(data.block_height)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    checkHealth()
    fetchBlockHeight()
    const interval = setInterval(() => {
      checkHealth()
      fetchBlockHeight()
    }, 10_000)
    return () => clearInterval(interval)
  }, [checkHealth, fetchBlockHeight])

  const statusColor = {
    online: '#22c55e',
    degraded: '#f59e0b',
    offline: '#ef4444',
  }[apiHealth] || '#64748b'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220,
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>
            ⬡ VaultWatch
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            DeFi Risk Intelligence
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '8px 8px', overflowY: 'auto' }}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: statusColor, flexShrink: 0,
            }} />
            <span style={{ color: 'var(--text-muted)' }}>
              API {apiHealth || 'checking...'}
            </span>
          </div>
          {blockHeight && (
            <div style={{ color: 'var(--text-muted)' }}>
              Block #{blockHeight.toLocaleString()}
            </div>
          )}
          <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>
            v4.0.0 · casper-test
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {activeTab === 'risk' && <RiskPanel apiUrl={API_URL} />}
        {activeTab === 'anomaly' && <AnomalyPanel apiUrl={API_URL} />}
        {activeTab === 'rwa' && <RWAPanel apiUrl={API_URL} />}
        {activeTab === 'audit' && <AuditPanel apiUrl={API_URL} />}
        {activeTab === 'chain' && <ChainStatus apiUrl={API_URL} />}
      </main>
    </div>
  )
}
