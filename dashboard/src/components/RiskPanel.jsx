import { useState, useEffect } from 'react'

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
  HIGH:     '#f59e0b',
  MEDIUM:   '#3b82f6',
  LOW:      '#22c55e',
}

const SEVERITY_BG = {
  CRITICAL: '#3a0a0a',
  HIGH:     '#2a1a00',
  MEDIUM:   '#0a1a3a',
  LOW:      '#0a2a0a',
}

function FindingCard({ f }) {
  const color = SEVERITY_COLOR[f.severity] || '#64748b'
  const bg = SEVERITY_BG[f.severity] || '#1a1a1a'
  const age = Math.round((Date.now() - f.timestamp) / 60000)
  const ageStr = age < 60 ? `${age}m ago` : `${Math.round(age / 60)}h ago`

  return (
    <div style={{
      padding: '14px 16px',
      background: 'var(--surface2)',
      borderRadius: 8,
      marginBottom: 8,
      fontSize: 13,
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{f.protocol}</span>
          <span style={{ fontFamily: 'monospace', fontSize: 10, color: 'var(--text-muted)' }}>{f.id}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{ageStr}</span>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
            background: color + '22', color,
          }}>{f.severity}</span>
        </div>
      </div>
      <div style={{ color: 'var(--text-muted)', marginBottom: 8, lineHeight: 1.5 }}>{f.summary}</div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Contract link — clearly labeled as contract verification */}
        <a
          href={`https://testnet.cspr.live/contract-package/${f.contract_hash}`}
          target="_blank" rel="noopener noreferrer"
          style={{
            color: 'var(--accent)', fontSize: 11, fontFamily: 'monospace',
            textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          ⬡ {f.contract} contract ↗
        </a>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Via: {f.agent}
        </span>
        {f.confidence && (
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            Confidence: {(f.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  )
}

export default function RiskPanel({ api }) {
  const [query, setQuery] = useState('')
  const [protocol, setProtocol] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [findings, setFindings] = useState([])
  const [findingsLoading, setFindingsLoading] = useState(false)

  const loadFindings = async () => {
    setFindingsLoading(true)
    try {
      const data = await api.getFindings(20)
      setFindings(data.findings || [])
    } catch {
      setFindings([])
    } finally {
      setFindingsLoading(false)
    }
  }

  useEffect(() => { loadFindings() }, [])

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.riskQuery({ query, protocol: protocol || undefined })
      setResult(data.result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Risk Intelligence</h1>
        <span style={{
          background: '#0a2a0a', border: '1px solid #22c55e40',
          color: '#22c55e', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4, letterSpacing: 0.5,
        }}>
          ● LIVE GROQ AI
        </span>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        Real-time DeFi risk analysis powered by llama-3.3-70b-versatile + Casper Testnet · Results written to RiskOracle contract.
      </p>

      {/* Query box */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Query VaultWatch AI Agent</h2>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. What are the main risk factors for CasperSwap?&#10;e.g. Analyze governance risks on CasperLend&#10;e.g. Is the CSPR/USDC liquidity pool safe for large positions?"
          style={{
            width: '100%', background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 8, color: 'var(--text)', padding: 12, fontSize: 13,
            resize: 'vertical', minHeight: 88, outline: 'none', marginBottom: 10,
            boxSizing: 'border-box', lineHeight: 1.5,
          }}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleQuery() }}
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
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            style={{ ...BTN, opacity: loading || !query.trim() ? 0.5 : 1 }}
          >
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12 }}>⟳</span> Analyzing via Groq...
              </span>
            ) : 'Analyze Risk'}
          </button>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Ctrl+Enter</span>
        </div>
      </div>

      {error && (
        <div style={{ ...CARD, borderColor: 'var(--danger)', background: '#1a0a0a', marginBottom: 16 }}>
          <span style={{ color: 'var(--danger)', fontSize: 13 }}>⚠ {error}</span>
        </div>
      )}

      {result && (
        <div style={{ ...CARD, borderColor: 'var(--accent)', borderWidth: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: 'var(--accent)' }}>
              Live Analysis Result
            </h3>
            {result.severity && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                background: (SEVERITY_COLOR[result.severity] || '#64748b') + '22',
                color: SEVERITY_COLOR[result.severity] || 'var(--text-muted)',
              }}>{result.severity}</span>
            )}
            {result.groq_model && (
              <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {result.groq_model}
              </span>
            )}
          </div>

          <p style={{ marginBottom: 12, lineHeight: 1.6, fontSize: 13 }}>
            {result.summary || result.content}
          </p>

          {result.risk_factors && result.risk_factors.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Risk Factors Identified
              </div>
              {result.risk_factors.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  padding: '6px 0', borderBottom: i < result.risk_factors.length - 1 ? '1px solid var(--border)' : 'none',
                  fontSize: 13,
                }}>
                  <span style={{ color: '#f59e0b', flexShrink: 0, marginTop: 1 }}>▸</span>
                  <span style={{ color: 'var(--text)' }}>{f}</span>
                </div>
              ))}
            </div>
          )}

          {result.recommendation && (
            <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '10px 12px', marginBottom: 10, fontSize: 13 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Recommendation · </span>
              {result.recommendation}
            </div>
          )}

          <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--text-muted)', alignItems: 'center', flexWrap: 'wrap' }}>
            {result.confidence !== undefined && (
              <span>Confidence: <strong style={{ color: 'var(--text)' }}>{(result.confidence * 100).toFixed(0)}%</strong></span>
            )}
            {result.on_chain_contract && (
              <span>
                Written to:{' '}
                <a
                  href={`https://testnet.cspr.live/contract-package/${result.on_chain_hash}`}
                  target="_blank" rel="noopener noreferrer"
                  style={{ color: 'var(--accent)', fontFamily: 'monospace' }}
                >
                  {result.on_chain_contract} ↗
                </a>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Findings feed */}
      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
            Agent Pipeline Findings
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
              logged to Casper contracts
            </span>
          </h2>
          <button onClick={loadFindings} disabled={findingsLoading}
            style={{ ...BTN, padding: '6px 14px', fontSize: 12, background: 'var(--surface2)', color: 'var(--text)' }}>
            {findingsLoading ? '...' : 'Refresh'}
          </button>
        </div>
        {findings.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading findings from pipeline...</p>
        ) : (
          findings.map((f, i) => <FindingCard key={i} f={f} />)
        )}
      </div>
    </div>
  )
}
