import { useState, useEffect } from 'react'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }

export default function AuditPanel({ apiFetch }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [limit, setLimit] = useState(50)
  const [writeForm, setWriteForm] = useState({ action: '', actor: '', details: '' })
  const [writeResult, setWriteResult] = useState(null)

  const loadLog = async () => {
    setLoading(true)
    try {
      const data = await apiFetch(`/audit/log?limit=${limit}`)
      setEntries(data.entries || [])
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadLog() }, [limit])

  const handleWrite = async () => {
    const params = new URLSearchParams({
      action: writeForm.action,
      actor: writeForm.actor,
      details: writeForm.details,
    })
    const data = await apiFetch(`/audit/write?${params}`, { method: 'POST' })
    setWriteResult(data)
    loadLog()
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Audit Log</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        On-chain audit trail — all agent actions recorded via AuditTrail.rs contract on Casper testnet.
      </p>

      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Audit Entries ({entries.length})</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', padding: '6px 10px', fontSize: 13 }}>
              {[10, 25, 50, 100, 200].map(n => <option key={n} value={n}>Last {n}</option>)}
            </select>
            <button onClick={loadLog} disabled={loading}
              style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
              {loading ? '...' : 'Refresh'}
            </button>
          </div>
        </div>

        {entries.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No audit entries found.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>#</th>
                  <th style={{ padding: '8px 12px' }}>Action</th>
                  <th style={{ padding: '8px 12px' }}>Actor</th>
                  <th style={{ padding: '8px 12px' }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)', opacity: 0.9 }}>
                    <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{e.id || i + 1}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--accent)', fontFamily: 'monospace', fontSize: 12 }}>{e.action}</td>
                    <td style={{ padding: '8px 12px' }}>{e.actor}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-muted)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Write Audit Entry (Demo)</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
          Simulates writing to AuditTrail.rs contract on Casper testnet.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Action</label>
            <input value={writeForm.action} onChange={e => setWriteForm(f => ({ ...f, action: e.target.value }))}
              placeholder="e.g. policy_update"
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Actor</label>
            <input value={writeForm.actor} onChange={e => setWriteForm(f => ({ ...f, actor: e.target.value }))}
              placeholder="e.g. AuditAgent"
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }} />
          </div>
        </div>
        <input value={writeForm.details} onChange={e => setWriteForm(f => ({ ...f, details: e.target.value }))}
          placeholder="Details (optional)"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%', marginBottom: 10 }} />
        <button onClick={handleWrite} disabled={!writeForm.action || !writeForm.actor}
          style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontSize: 14, fontWeight: 600, opacity: (!writeForm.action || !writeForm.actor) ? 0.5 : 1 }}>
          Submit Entry
        </button>
        {writeResult && (
          <p style={{ marginTop: 8, color: 'var(--success)', fontSize: 13 }}>
            Submitted — deploy hash: <span style={{ fontFamily: 'monospace' }}>{writeResult.deploy_hash?.slice(0, 32)}...</span>
          </p>
        )}
      </div>
    </div>
  )
}
