import { useState, useEffect, useCallback } from 'react'
import RiskPanel from './components/RiskPanel.jsx'
import AnomalyPanel from './components/AnomalyPanel.jsx'
import RWAPanel from './components/RWAPanel.jsx'
import AuditPanel from './components/AuditPanel.jsx'
import ChainStatus from './components/ChainStatus.jsx'
import { mockApi } from './mockApi.js'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Check if the real API is reachable; if not, fall back to mock
let _useMock = null
export async function checkApiMode() {
  if (_useMock !== null) return _useMock
  try {
    const ctrl = new AbortController()
    const tid = setTimeout(() => ctrl.abort(), 3000)
    const r = await fetch(`${API_URL}/health`, { signal: ctrl.signal })
    clearTimeout(tid)
    _useMock = !r.ok
  } catch {
    _useMock = true
  }
  return _useMock
}

// Unified fetch that falls back to mock on failure
export async function apiFetch(path, opts = {}) {
  const useMock = await checkApiMode()
  if (!useMock) {
    try {
      const r = await fetch(`${API_URL}${path}`, opts)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    } catch {
      // fall through to mock
    }
  }
  // Route to mock
  if (path === '/health') return mockApi.health()
  if (path.startsWith('/chain/block')) return mockApi.getBlock()
  if (path.startsWith('/risk/findings')) {
    const limit = new URL(`http://x${path}`).searchParams.get('limit') || 20
    return mockApi.getFindings(Number(limit))
  }
  if (path === '/risk/query') {
    const body = opts.body ? JSON.parse(opts.body) : {}
    return mockApi.riskQuery(body)
  }
  if (path === '/anomaly/detect') {
    const body = opts.body ? JSON.parse(opts.body) : {}
    return mockApi.detectAnomaly(body)
  }
  if (path === '/rwa/assess') {
    const body = opts.body ? JSON.parse(opts.body) : {}
    return mockApi.assessRWA(body)
  }
  if (path === '/rwa/assets') return mockApi.getRWAAssets()
  if (path.startsWith('/audit/log')) return mockApi.getAuditLog()
  if (path.startsWith('/audit/write')) {
    const url = new URL(`http://x${path}`)
    return mockApi.writeAudit({
      action: url.searchParams.get('action'),
      actor: url.searchParams.get('actor'),
      details: url.searchParams.get('details'),
    })
  }
  if (path === '/metrics/spans') return mockApi.getSpans()
  throw new Error(`Unknown path: ${path}`)
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
  const [apiHealth, setApiHealth] = useState(null)
  const [blockHeight, setBlockHeight] = useState(null)
  const [isDemoMode, setIsDemoMode] = useState(false)

  const checkHealth = useCallback(async () => {
    try {
      const data = await apiFetch('/health')
      setApiHealth(data.status === 'ok' ? 'online' : 'degraded')
      setIsDemoMode(!!data.mode && data.mode === 'demo')
    } catch {
      setApiHealth('offline')
    }
  }, [])

  const fetchBlockHeight = useCallback(async () => {
    try {
      const data = await apiFetch('/chain/block')
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
            DeFi Risk Intelligence · Casper
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
              background: isDemoMode ? '#f59e0b' : statusColor, flexShrink: 0,
            }} />
            <span style={{ color: 'var(--text-muted)' }}>
              {isDemoMode ? 'Demo mode' : `API ${apiHealth || 'checking...'}`}
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
          {isDemoMode && (
            <div style={{
              marginTop: 8,
              background: '#2a1f00',
              border: '1px solid #f59e0b30',
              borderRadius: 6,
              padding: '6px 8px',
              fontSize: 10,
              color: '#f59e0b',
              lineHeight: 1.4,
            }}>
              Live demo — real testnet TX hashes from Casper testnet
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {activeTab === 'risk' && <RiskPanel apiFetch={apiFetch} />}
        {activeTab === 'anomaly' && <AnomalyPanel apiFetch={apiFetch} />}
        {activeTab === 'rwa' && <RWAPanel apiFetch={apiFetch} />}
        {activeTab === 'audit' && <AuditPanel apiFetch={apiFetch} />}
        {activeTab === 'chain' && <ChainStatus apiFetch={apiFetch} />}
      </main>
    </div>
  )
}
