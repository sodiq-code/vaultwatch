import { useState, useEffect } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }

const ACTION_COLORS = {
  scan_complete:     '#3b82f6',
  finding_written:   '#22c55e',
  risk_score_updated:'#22c55e',
  alert_dispatched:  '#ef4444',
  self_correction:   '#f59e0b',
  rwa_assessed:      '#a78bfa',
  policy_updated:    '#06b6d4',
  x402_payment:      '#f59e0b',
  behavior_indexed:  '#3b82f6',
  safety_blocked:    '#ef4444',
}

export default function AuditPanel({ api }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [limit, setLimit] = useState(50)
  const [writeForm, setWriteForm] = useState({ action: '', actor: '', details: '' })
  const [writeResult, setWriteResult] = useState(null)
  const [writing, setWriting] = useState(false)

  const loadLog = async () => {
    setLoading(true)
    try {
      const data = await api.getAuditLog(limit)
      setEntries(data.entries || [])
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadLog() }, [limit])

  const handleWrite = async () => {
    if (!writeForm.action || !writeForm.actor) return
    setWriting(true)
    setWriteResult(null)
    try {
      const data = await api.writeAudit(writeForm)
      setWriteResult(data)
      loadLog()
    } finally {
      setWriting(false)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Audit Log</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        On-chain audit trail — all agent actions recorded via AuditTrail contract on Casper Testnet.{' '}
        <a
          href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.AuditTrail}`}
          target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--accent)', fontSize: 12 }}
        >
          View AuditTrail deploy ↗
        </a>
      </p>

      {/* Agent pipeline activity */}
      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
            Pipeline Activity Log <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>({entries.length} entries)</span>
          </h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', padding: '6px 10px', fontSize: 13, outline: 'none' }}>
              {[10, 25, 50, 100].map(n => <option key={n} value={n}>Last {n}</option>)}
            </select>
            <button onClick={loadLog} disabled={loading}
              style={{ background: 'var(--surface2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
              {loading ? '...' : 'Refresh'}
            </button>
          </div>
        </div>

        {entries.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No audit entries.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px', width: 40 }}>#</th>
                  <th style={{ padding: '8px 12px' }}>Action</th>
                  <th style={{ padding: '8px 12px' }}>Agent</th>
                  <th style={{ padding: '8px 12px' }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => {
                  const actionColor = ACTION_COLORS[e.action] || 'var(--accent)'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px', color: 'var(--text-muted)', fontSize: 12 }}>{e.id || i + 1}</td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{
                          fontFamily: 'monospace', fontSize: 11,
                          background: actionColor + '18', color: actionColor,
                          padding: '2px 8px', borderRadius: 4, fontWeight: 600,
                        }}>
                          {e.action}
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px', fontWeight: 600, fontSize: 12 }}>{e.actor}</td>
                      <td style={{
                        padding: '8px 12px', color: 'var(--text-muted)',
                        maxWidth: 320, overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        fontSize: 12,
                      }} title={e.details}>
                        {e.details}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Write demo */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Write Audit Entry</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 14 }}>
          Simulates AuditAgent writing to the{' '}
          <a href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.AuditTrail}`}
            target="_blank" rel="noopener noreferrer"
            style={{ color: 'var(--accent)' }}>
            AuditTrail deploy ↗
          </a>{' '}
          on Casper Testnet.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Action</label>
            <input value={writeForm.action} onChange={e => setWriteForm(f => ({ ...f, action: e.target.value }))}
              placeholder="e.g. policy_update"
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Actor (Agent)</label>
            <input value={writeForm.actor} onChange={e => setWriteForm(f => ({ ...f, actor: e.target.value }))}
              placeholder="e.g. AuditAgent"
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }} />
          </div>
        </div>
        <input value={writeForm.details} onChange={e => setWriteForm(f => ({ ...f, details: e.target.value }))}
          placeholder="Details (optional)"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%', marginBottom: 10 }} />
        <button
          onClick={handleWrite}
          disabled={!writeForm.action || !writeForm.actor || writing}
          style={{
            background: 'var(--accent)', color: '#fff', border: 'none',
            borderRadius: 8, padding: '10px 20px', cursor: 'pointer',
            fontSize: 14, fontWeight: 600,
            opacity: (!writeForm.action || !writeForm.actor || writing) ? 0.5 : 1,
          }}>
          {writing ? '⟳ Submitting...' : 'Submit to AuditTrail'}
        </button>

        {writeResult && (
          <div style={{ marginTop: 10, background: '#0a2a0a', border: '1px solid #22c55e30', borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ color: '#22c55e', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              ✓ Entry submitted
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Simulated deploy hash:{' '}
              <span style={{ fontFamily: 'monospace', color: 'var(--text)' }}>
                {writeResult.deploy_hash?.slice(0, 32)}...
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Block: #{writeResult.block_height?.toLocaleString()} · Contract: AuditTrail
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
