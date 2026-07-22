/**
 * RiskPanel — Enhanced risk intelligence with findings feed, risk query, and severity breakdown.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SeverityBadge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { SkeletonBlock, SkeletonLine } from '../ui/Skeleton.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'
import { RiskGaugeChart } from '../charts/RiskGaugeChart.jsx'
import { AgentActivityChart } from '../charts/AgentActivityChart.jsx'

export function RiskPanel({ api, addToast }) {
  const [findings, setFindings] = useState([])
  const [riskScore, setRiskScore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [protocol, setProtocol] = useState('')
  const [queryResult, setQueryResult] = useState(null)
  const [queryLoading, setQueryLoading] = useState(false)
  const [source, setSource] = useState('fallback')

  useEffect(() => {
    loadFindings()
    const interval = setInterval(loadFindings, 20000)
    return () => clearInterval(interval)
  }, [])

  const loadFindings = async () => {
    try {
      const data = await api.fetchLiveFindings(20)
      if (data?.findings) {
        setFindings(data.findings)
        setSource(data.source || 'fallback')
      }
    } catch (e) {
      // Keep stale data
    } finally {
      setLoading(false)
    }
  }

  const handleRiskQuery = async () => {
    if (!query.trim()) return
    setQueryLoading(true)
    setQueryResult(null)
    try {
      const result = await api.riskQuery({ query, protocol })
      setQueryResult(result)
      addToast({ type: 'success', message: 'Risk query completed' })
    } catch (e) {
      addToast({ type: 'error', message: `Risk query failed: ${e.message}` })
    } finally {
      setQueryLoading(false)
    }
  }

  const maxRiskScore = findings.length
    ? Math.max(...findings.map(f => Math.round((f.confidence || 0) * 100)))
    : 0

  const severityCounts = findings.reduce((acc, f) => {
    const s = f.severity || 'UNKNOWN'
    acc[s] = (acc[s] || 0) + 1
    return acc
  }, {})

  const agentCounts = findings.reduce((acc, f) => {
    const a = f.agent?.split('→')[0]?.trim() || 'Unknown'
    acc[a] = (acc[a] || 0) + 1
    return acc
  }, {})

  const agentData = Object.entries(agentCounts).map(([agent, count]) => ({ agent, count }))

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} />
      </div>
    )
  }

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Risk Intelligence"
        subtitle="AI-powered risk analysis with on-chain findings feed"
        icon="🛡️"
        source={source}
      />

      {/* Stats row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="Findings" value={findings.length} icon="🔍" color="var(--accent)" />
        <StatCard label="Max Risk Score" value={maxRiskScore} suffix="/100" icon="⚡" color={maxRiskScore > 70 ? 'var(--danger)' : 'var(--warning)'} />
        <StatCard label="Critical" value={severityCounts.CRITICAL || 0} icon="🔴" color="var(--danger)" />
        <StatCard label="High" value={severityCounts.HIGH || 0} icon="🟠" color="var(--warning)" />
      </div>

      {/* Two column: Risk Query + Gauge */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        marginBottom: 'var(--space-lg)',
      }}>
        {/* Risk query panel */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Risk Query
          </div>
          <Input
            label="Query"
            value={query}
            onChange={setQuery}
            placeholder="e.g., whale concentration CasperSwap"
            icon="🔍"
            clearable
            onKeyDown={(e) => e.key === 'Enter' && handleRiskQuery()}
          />
          <Input
            label="Protocol"
            value={protocol}
            onChange={setProtocol}
            placeholder="e.g., CasperSwap (optional)"
            icon="🔗"
            style={{ marginTop: 'var(--space-sm)' }}
          />
          <GradientBtn
            variant="primary"
            onClick={handleRiskQuery}
            loading={queryLoading}
            disabled={!query.trim()}
            fullWidth
            style={{ marginTop: 'var(--space-md)' }}
          >
            Analyze Risk
          </GradientBtn>

          {/* Query result */}
          {queryResult && (
            <div className="slide-up" style={{
              marginTop: 'var(--space-lg)',
              padding: 'var(--space-md)',
              background: 'rgba(0, 212, 255, 0.06)',
              border: '1px solid var(--border2)',
              borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
                <SeverityBadge severity={queryResult.result?.severity || 'MEDIUM'} />
                <SourceBadge source={queryResult._source} />
              </div>
              <div style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
                marginBottom: 'var(--space-sm)',
              }}>
                {queryResult.result?.summary}
              </div>
              <div style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--accent)',
                fontWeight: 'var(--font-weight-medium)',
                marginBottom: 'var(--space-sm)',
              }}>
                Recommendation: {queryResult.result?.recommendation}
              </div>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                Confidence: {((queryResult.result?.confidence || 0) * 100).toFixed(1)}% • Model: {queryResult.result?.groq_model || 'unknown'}
              </div>
            </div>
          )}
        </GlassCard>

        {/* Gauge + Agent chart */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          <GlassCard hover={false} style={{
            padding: 'var(--space-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <RiskGaugeChart score={maxRiskScore} size={180} />
          </GlassCard>
          <GlassCard hover={false} style={{ padding: 'var(--space-md)' }}>
            <div style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-semibold)',
              color: 'var(--text-secondary)',
              marginBottom: 'var(--space-sm)',
            }}>
              Agent Activity
            </div>
            {agentData.length > 0 && <AgentActivityChart data={agentData} height={140} />}
          </GlassCard>
        </div>
      </div>

      {/* Findings feed */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text)',
          marginBottom: 'var(--space-md)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}>
          Findings Feed
          <Badge size="sm" colorScheme="accent">{findings.length} total</Badge>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {findings.map((finding, i) => (
            <div key={finding.id || i} className={`glass-row-hover stagger-${Math.min(i + 1, 6)}`} style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 'var(--space-md)',
              padding: 'var(--space-md)',
              background: 'rgba(14, 18, 30, 0.4)',
              borderRadius: 'var(--radius-md)',
              borderLeft: `3px solid ${
                finding.severity === 'CRITICAL' ? 'var(--danger)' :
                finding.severity === 'HIGH' ? '#ff6b7a' :
                finding.severity === 'MEDIUM' ? 'var(--warning)' : 'var(--info)'
              }`,
            }}>
              <SeverityBadge severity={finding.severity} />
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 'var(--font-size-md)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--text)',
                  marginBottom: 4,
                }}>
                  {finding.protocol} — {finding.risk_type}
                </div>
                <div style={{
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.4,
                }}>
                  {finding.summary}
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  marginTop: 'var(--space-xs)',
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                }}>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{((finding.confidence || 0) * 100).toFixed(0)}% conf</span>
                  <span>•</span>
                  <span>{finding.agent}</span>
                  <span>•</span>
                  <span>{new Date(finding.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
              <SourceBadge source={finding.source || source} />
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}

export default RiskPanel
