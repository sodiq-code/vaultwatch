import { useState } from 'react'
import { mockApi } from '../mockApi.js'

const CARD = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: 20,
  marginBottom: 16,
}

const BTN = {
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '10px 20px',
  cursor: 'pointer',
  fontSize: 14,
  fontWeight: 600,
}

const SEVERITY_COLOR = {
  CRITICAL: '#ef4444',
  HIGH: '#f59e0b',
  MEDIUM: '#3b82f6',
  LOW: '#22c55e',
}

export default function RiskPanel({ apiFetch }) {
  const [query, setQuery] = useState('')
  const [protocol, setProtocol] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [findings, setFindings] = useState([])
  const [findingsLoading, setFindingsLoading] = useState(false)

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiFetch('/risk/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, protocol: protocol || undefined }),
      })
      setResult(data.result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadFindings = async () => {
    setFindingsLoading(true)
    try {
      const data = await apiFetch('/risk/findings?limit=20')
      setFindings(data.findings || [])
    } catch {
      setFindings([])
    } finally {
      setFindingsLoading(false)
    }
  }

  // Load findings on mount
  useState(() => { loadFindings() })

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Risk Intelligence</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        Query the AI agent pipeline for DeFi protocol risk analysis powered by Groq + Casper Sidecar SSE.
      </p>

      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Ask the Risk Agent</h2>
        <textarea
          data-testid="risk-query-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. What are the main risk factors for CasperSwap? | What is the whale concentration on CasperLend?"
          style={{
            width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 8, color: 'var(--text)', padding: 12, fontSize: 14,
            resize: 'vertical', minHeight: 80, outline: 'none', marginBottom: 10,
            boxSizing: 'border-box',
          }}
          onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleQuery() }}
        />
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            value={protocol}
            onChange={e => setProtocol(e.target.value)}
            placeholder="Protocol (optional)"
            style={{
              background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 8, color: 'var(--text)', padding: '10px 12px',
              fontSize: 13, outline: 'none', width: 180,
            }}
          />
          <button
            data-testid="query-submit"
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            style={{ ...BTN, opacity: loading || !query.trim() ? 0.5 : 1 }}
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Ctrl+Enter</span>
        </div>
      </div>

      {error && (
        <div style={{ ...CARD, borderColor: 'var(--danger)', background: '#1a0a0a' }}>
          <span style={{ color: 'var(--danger)' }}>Error: {error}</span>
        </div>
      )}

      {result && (
        <div style={{ ...CARD, borderColor: 'var(--accent)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, color: 'var(--accent)' }}>
            Analysis Result
            {result.groq_model && (
              <span style={{ fontWeight: 400, marginLeft: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                via {result.groq_model}
              </span>
            )}
          </h3>
          <p style={{ marginBottom: 8 }}>{result.summary || result.content || JSON.stringify(result)}</p>
          {result.risk_factors && result.risk_factors.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <strong style={{ fontSize: 12, color: 'var(--text-muted)' }}>Risk Factors:</strong>
              <ul style={{ marginTop: 4, paddingLeft: 18 }}>
                {result.risk_factors.map((f, i) => (
                  <li key={i} style={{ color: 'var(--warning)', fontSize: 13 }}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          {result.confidence !== undefined && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
              Confidence: {(result.confidence * 100).toFixed(0)}%
            </div>
          )}
          {result.on_chain_hash && (
            <div style={{ marginTop: 8, fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>On-chain: </span>
              <a
                href={`https://testnet.cspr.live/deploy/${result.on_chain_hash}`}
                target="_blank" rel="noopener noreferrer"
                style={{ color: 'var(--accent)', fontFamily: 'monospace' }}
              >
                {result.on_chain_hash.slice(0, 20)}...
              </a>
            </div>
          )}
        </div>
      )}

      <div style={{ ...CARD }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>Recent Findings from Casper Testnet</h2>
          <button onClick={loadFindings} disabled={findingsLoading}
            style={{ ...BTN, padding: '6px 14px', fontSize: 12, background: 'var(--surface2)', color: 'var(--text)' }}>
            {findingsLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        {findings.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading findings...</p>
        ) : (
          findings.map((f, i) => (
            <div key={i} style={{
              padding: '12px 14px', background: 'var(--surface2)',
              borderRadius: 8, marginBottom: 8, fontSize: 13,
              borderLeft: `3px solid ${SEVERITY_COLOR[f.severity] || 'var(--border)'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>{f.protocol || 'Unknown protocol'}</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                  background: (SEVERITY_COLOR[f.severity] || '#64748b') + '22',
                  color: SEVERITY_COLOR[f.severity] || 'var(--text-muted)',
                }}>{f.severity}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{f.summary}</div>
              {f.tx_hash && (
                <div style={{ fontSize: 11 }}>
                  <a
                    href={`https://testnet.cspr.live/deploy/${f.tx_hash}`}
                    target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)', fontFamily: 'monospace' }}
                  >
                    {f.tx_hash.slice(0, 16)}... ↗
                  </a>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
