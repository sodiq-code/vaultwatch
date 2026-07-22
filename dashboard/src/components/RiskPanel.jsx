import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'

const SEVERITY_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f59e0b',
  MEDIUM:   '#3b82f6',
  LOW:      '#22c55e',
}

const SEVERITY_GLOW = {
  CRITICAL: 'danger',
  HIGH:     'warning',
  MEDIUM:   undefined,
  LOW:      'success',
}

function FindingCard({ f }) {
  const color = SEVERITY_COLOR[f.severity] || '#64748b'
  const glow = SEVERITY_GLOW[f.severity]
  const age = Math.round((Date.now() - f.timestamp) / 60000)
  const ageStr = age < 60 ? `${age}m ago` : `${Math.round(age / 60)}h ago`

  return (
    <GlassCard glow={glow} style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 'var(--font-weight-bold)', fontSize: 'var(--font-size-md)' }}>{f.protocol}</span>
          <span style={{ fontFamily: 'var(--font)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>{f.id}</span>
          {f.source && <SourceBadge source={f.source} />}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>{ageStr}</span>
          <Badge>{f.severity}</Badge>
        </div>
      </div>
      <div style={{ color: 'var(--text-muted)', marginBottom: 8, lineHeight: 1.5, fontSize: 'var(--font-size-sm)' }}>{f.summary}</div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <a
          href={`https://testnet.cspr.live/deploy/${f.contract_hash}`}
          target="_blank" rel="noopener noreferrer"
          style={{
            color: 'var(--accent)', fontSize: 'var(--font-size-xs)', fontFamily: 'var(--font)',
            textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          ⬡ {f.contract} deploy ↗
        </a>
        <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
          Via: {f.agent}
        </span>
        {f.confidence && (
          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
            Confidence: {(f.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </GlassCard>
  )
}

export default function RiskPanel({ api, addToast }) {
  const [query, setQuery] = useState('')
  const [protocol, setProtocol] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [findings, setFindings] = useState([])
  const [findingsLoading, setFindingsLoading] = useState(false)
  const [findingsSource, setFindingsSource] = useState('seed')

  const loadFindings = async () => {
    setFindingsLoading(true)
    try {
      const data = await api.getFindings(20)
      setFindings(data.findings || [])
      setFindingsSource(data._source || data.source || 'seed')
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
      addToast({ type: 'success', message: 'Risk analysis completed successfully' })
    } catch (e) {
      setError(e.message)
      addToast({ type: 'error', message: `Risk query failed: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        icon="🔍"
        badge="AI"
        title="Risk Intelligence"
        subtitle="Real-time DeFi risk analysis powered by llama-3.3-70b-versatile + Casper Testnet · Results written to RiskOracle contract."
      />

      {/* Query box */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
          Query VaultWatch AI Agent
        </h2>
        <Input
          type="textarea"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. What are the main risk factors for CasperSwap?\ne.g. Analyze governance risks on CasperLend\ne.g. Is the CSPR/USDC liquidity pool safe for large positions?"
          style={{ marginBottom: 'var(--space-sm)' }}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleQuery() }}
        />
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Input
            value={protocol}
            onChange={e => setProtocol(e.target.value)}
            placeholder="Protocol (optional)"
            style={{ width: 180 }}
          />
          <GradientBtn
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            loading={loading}
          >
            {loading ? 'Analyzing via Groq...' : 'Analyze Risk'}
          </GradientBtn>
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>Ctrl+Enter</span>
        </div>
      </GlassCard>

      {error && (
        <GlassCard glow="danger" style={{ marginBottom: 'var(--space-md)' }}>
          <span style={{ color: 'var(--danger)', fontSize: 'var(--font-size-sm)' }}>⚠ {error}</span>
        </GlassCard>
      )}

      {loading && !result && (
        <SkeletonCard style={{ marginBottom: 'var(--space-md)' }} />
      )}

      {result && (
        <GlassCard glow={result.severity ? SEVERITY_GLOW[result.severity] : undefined} style={{ marginBottom: 'var(--space-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--space-md)' }}>
            <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-bold)', margin: 0, color: 'var(--accent)' }}>
              Live Analysis Result
            </h3>
            {result.severity && <Badge>{result.severity}</Badge>}
            {result._source && <SourceBadge source={result._source} />}
            {result.groq_model && (
              <span style={{ fontWeight: 'var(--font-weight-normal)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {result.groq_model}
              </span>
            )}
          </div>

          <p style={{ marginBottom: 'var(--space-md)', lineHeight: 1.6, fontSize: 'var(--font-size-sm)' }}>
            {result.summary || result.content}
          </p>

          {result.risk_factors && result.risk_factors.length > 0 && (
            <div style={{ marginBottom: 'var(--space-md)' }}>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Risk Factors Identified
              </div>
              {result.risk_factors.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  padding: 'var(--space-xs) 0',
                  borderBottom: i < result.risk_factors.length - 1 ? '1px solid var(--border)' : 'none',
                  fontSize: 'var(--font-size-sm)',
                }}>
                  <span style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 1 }}>▸</span>
                  <span style={{ color: 'var(--text)' }}>{f}</span>
                </div>
              ))}
            </div>
          )}

          {result.recommendation && (
            <GlassCard glow="success" style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-sm)' }}>
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Recommendation · </span>
              <span style={{ fontSize: 'var(--font-size-sm)' }}>{result.recommendation}</span>
            </GlassCard>
          )}

          <div style={{ display: 'flex', gap: 16, fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', alignItems: 'center', flexWrap: 'wrap' }}>
            {result.confidence !== undefined && (
              <span>Confidence: <strong style={{ color: 'var(--text)' }}>
                <AnimatedCounter value={result.confidence * 100} formatter={v => `${Math.round(v)}%`} />
              </strong></span>
            )}
            {result.on_chain_contract && (
              <span>
                Written to:{' '}
                <a
                  href={`https://testnet.cspr.live/deploy/${result.on_chain_hash}`}
                  target="_blank" rel="noopener noreferrer"
                  style={{ color: 'var(--accent)', fontFamily: 'var(--font)' }}
                >
                  {result.on_chain_contract} deploy ↗
                </a>
              </span>
            )}
          </div>
        </GlassCard>
      )}

      {/* Findings feed */}
      <GlassCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', margin: 0 }}>
            Agent Pipeline Findings
            <SourceBadge source={findingsSource} />
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontWeight: 'var(--font-weight-normal)', marginLeft: 8 }}>
              logged to Casper contracts
            </span>
          </h2>
          <GradientBtn
            variant="ghost"
            size="sm"
            onClick={loadFindings}
            disabled={findingsLoading}
            loading={findingsLoading}
          >
            Refresh
          </GradientBtn>
        </div>
        {findingsLoading && findings.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <SkeletonLine width="100%" height={60} />
            <SkeletonLine width="100%" height={60} />
            <SkeletonLine width="80%" height={60} />
          </div>
        ) : findings.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>Loading findings from pipeline...</p>
        ) : (
          findings.map((f, i) => <FindingCard key={i} f={f} />)
        )}
      </GlassCard>
    </div>
  )
}
