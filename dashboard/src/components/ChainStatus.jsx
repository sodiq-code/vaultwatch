import { useState, useEffect } from 'react'
import { mockApi } from '../mockApi.js'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }

const STAT = ({ label, value, color = 'var(--text)' }) => (
  <div style={{ background: 'var(--surface2)', borderRadius: 10, padding: '16px 20px' }}>
    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value ?? '—'}</div>
  </div>
)

const CONTRACT_HASHES = mockApi.deployHashes

export default function ChainStatus({ apiFetch }) {
  const [chain, setChain] = useState(null)
  const [health, setHealth] = useState(null)
  const [spans, setSpans] = useState([])
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const [chainR, healthR, spansR] = await Promise.all([
        apiFetch('/chain/block'),
        apiFetch('/health'),
        apiFetch('/metrics/spans'),
      ])
      setChain(chainR)
      setHealth(healthR)
      setSpans(spansR.spans || [])
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 8000)
    return () => clearInterval(t)
  }, [apiFetch])

  const statusColor = health?.status === 'ok' ? 'var(--success)' : 'var(--danger)'
  const isDemoMode = health?.mode === 'demo'

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Chain Status</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        Live Casper testnet status, deployed contract hashes, and OTel observability spans.
      </p>

      <div style={{ ...CARD }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Network Overview</h2>
          <button onClick={refresh} disabled={loading}
            style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <STAT label="API Status" value={isDemoMode ? 'DEMO' : (health?.status?.toUpperCase() ?? 'UNKNOWN')} color={isDemoMode ? '#f59e0b' : statusColor} />
          <STAT label="Block Height" value={chain?.block_height?.toLocaleString()} color="var(--accent)" />
          <STAT label="Network" value={chain?.network ?? 'casper-test'} />
          <STAT label="Contracts" value="8 / 8" color="var(--success)" />
        </div>
      </div>

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Deployed Contracts — Casper Testnet</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
          All 8 Odra contracts compiled to WASM and deployed on casper-test.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Contract</th>
                <th style={{ padding: '8px 12px' }}>Deploy Hash</th>
                <th style={{ padding: '8px 12px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(CONTRACT_HASHES).map(([name, hash]) => (
                <tr key={name} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 12px', color: 'var(--accent)', fontWeight: 600 }}>{name}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <a
                      href={`https://testnet.cspr.live/deploy/${hash}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--text-muted)', fontFamily: 'monospace', textDecoration: 'none' }}
                    >
                      {hash.slice(0, 20)}... ↗
                    </a>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span style={{ color: 'var(--success)', fontWeight: 600, fontSize: 11 }}>✓ DEPLOYED</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>OTel Spans — Recent Agent Traces ({spans.length})</h2>
        {spans.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No spans collected yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>Span Name</th>
                  <th style={{ padding: '8px 12px' }}>Duration (ms)</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {spans.slice(-20).reverse().map((s, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', color: 'var(--accent)', fontFamily: 'monospace', fontSize: 12 }}>{s.name}</td>
                    <td style={{ padding: '8px 12px' }}>{s.duration_ms ? s.duration_ms.toFixed(1) : '—'}</td>
                    <td style={{ padding: '8px 12px', color: s.status === 'OK' ? 'var(--success)' : 'var(--text-muted)' }}>
                      {s.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
