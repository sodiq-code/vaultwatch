import { useState, useEffect } from 'react'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }

const STAT = ({ label, value, color = 'var(--text)' }) => (
  <div style={{ background: 'var(--surface2)', borderRadius: 10, padding: '16px 20px' }}>
    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value ?? '—'}</div>
  </div>
)

export default function ChainStatus({ apiUrl }) {
  const [chain, setChain] = useState(null)
  const [health, setHealth] = useState(null)
  const [spans, setSpans] = useState([])
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const [chainR, healthR, spansR] = await Promise.all([
        fetch(`${apiUrl}/chain/block`).then(r => r.json()),
        fetch(`${apiUrl}/health`).then(r => r.json()),
        fetch(`${apiUrl}/metrics/spans`).then(r => r.json()),
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
  }, [apiUrl])

  const statusColor = health?.status === 'ok' ? 'var(--success)' : 'var(--danger)'

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Chain Status</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>Live Casper network status and observability metrics.</p>

      <div style={{ ...CARD }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Network Overview</h2>
          <button onClick={refresh} disabled={loading}
            style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <STAT label="API Status" value={health?.status?.toUpperCase() ?? 'UNKNOWN'} color={statusColor} />
          <STAT label="Block Height" value={chain?.block_height?.toLocaleString()} color="var(--accent)" />
          <STAT label="Network" value={chain?.network ?? 'casper-test'} />
          <STAT label="API Version" value={health?.version ?? '4.0.0'} />
        </div>
      </div>

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Recent OTel Spans ({spans.length})</h2>
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
                    <td style={{ padding: '8px 12px', color: 'var(--accent)' }}>{s.name}</td>
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

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Contract Addresses</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 12 }}>
          Set in <code style={{ background: 'var(--surface2)', padding: '2px 6px', borderRadius: 4 }}>.env</code> after deployment.
        </p>
        {[
          'AUDIT_TRAIL_HASH',
          'RISK_ORACLE_HASH',
          'SENTINEL_CREDIT_HASH',
          'SENTINEL_REGISTRY_HASH',
          'SENTINEL_ALERT_LOG_HASH',
          'AGENT_BEHAVIOR_INDEX_HASH',
          'RISK_POLICY_MANAGER_HASH',
          'SUBSCRIBER_VAULT_HASH',
        ].map(key => (
          <div key={key} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '8px 12px', background: 'var(--surface2)', borderRadius: 8, marginBottom: 6, fontSize: 13,
          }}>
            <span style={{ color: 'var(--accent)', fontFamily: 'monospace' }}>{key}</span>
            <span style={{ color: 'var(--text-muted)' }}>Not deployed</span>
          </div>
        ))}
      </div>
    </div>
  )
}
