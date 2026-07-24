/**
 * LiveFeed — Enhanced agent event stream showing real-time findings,
 * audit log entries, and agent activity events.
 */
import { useState, useEffect, useRef } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { Badge, SeverityBadge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'
import { AgentActivityChart } from '../charts/AgentActivityChart.jsx'

export function LiveFeed({ api, addToast }) {
  const [findings, setFindings] = useState([])
  const [auditLog, setAuditLog] = useState([])
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState('fallback')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [activeView, setActiveView] = useState('findings')
  const containerRef = useRef(null)

  useEffect(() => {
    loadData()
    if (autoRefresh) {
      const interval = setInterval(loadData, 10000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  const loadData = async () => {
    try {
      const findingsData = await api.fetchLiveFindings(30)
      if (findingsData?.findings) {
        setFindings(prev => {
          // Only update if new findings exist
          if (findingsData.findings.length > prev.length) return findingsData.findings
          return prev
        })
        setSource(findingsData.source || 'fallback')
      }

      const auditData = await api.getAuditLog(15)
      if (auditData?.entries) {
        setAuditLog(auditData.entries)
      }
    } catch (e) {
      // Keep stale
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} />
      </div>
    )
  }

  // Agent activity chart data
  const agentCounts = findings.reduce((acc, f) => {
    const a = f.agent?.split('→')[0]?.trim() || 'Unknown'
    acc[a] = (acc[a] || 0) + 1
    return acc
  }, {})
  const chartData = Object.entries(agentCounts).map(([agent, count]) => ({ agent, count }))

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Agent Events"
        subtitle="Live event stream — findings, audit trail, agent activity"
        icon="📡"
        source={source}
        actions={
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <GradientBtn variant={autoRefresh ? 'primary' : 'ghost'} size="sm" onClick={() => setAutoRefresh(!autoRefresh)} icon="⟳">
              {autoRefresh ? 'Auto' : 'Manual'}
            </GradientBtn>
            <GradientBtn variant="ghost" size="sm" onClick={loadData} icon="🔄">
              Refresh
            </GradientBtn>
          </div>
        }
      />

      {/* Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="Active Findings" value={findings.length} icon="🔍" color="var(--accent)" />
        <StatCard label="Audit Entries" value={auditLog.length} icon="📋" color="var(--accent2)" />
        <StatCard label="Critical" value={findings.filter(f => f.severity === 'CRITICAL').length} icon="🔴" color="var(--danger)" />
        <StatCard label="Agents Active" value={Object.keys(agentCounts).length} icon="🧠" color="var(--success)" />
      </div>

      {/* View toggle */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <GradientBtn variant={activeView === 'findings' ? 'primary' : 'ghost'} size="sm" onClick={() => setActiveView('findings')}>
          Findings Feed
        </GradientBtn>
        <GradientBtn variant={activeView === 'audit' ? 'primary' : 'ghost'} size="sm" onClick={() => setActiveView('audit')}>
          Audit Trail
        </GradientBtn>
        <GradientBtn variant={activeView === 'chart' ? 'primary' : 'ghost'} size="sm" onClick={() => setActiveView('chart')}>
          Activity Chart
        </GradientBtn>
      </div>

      {activeView === 'findings' && (
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Live Findings Stream
          </div>
          <div ref={containerRef} style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
            maxHeight: 500,
            overflowY: 'auto',
          }}>
            {findings.map((finding, i) => (
              <div key={finding.id || i} className="slide-in-right" style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-md)',
                padding: 'var(--space-md)',
                background: i === 0 ? 'rgba(0, 212, 255, 0.08)' : 'rgba(14, 18, 30, 0.4)',
                borderRadius: 'var(--radius-md)',
                borderLeft: `3px solid ${
                  finding.severity === 'CRITICAL' ? 'var(--danger)' :
                  finding.severity === 'HIGH' ? '#ff6b7a' :
                  finding.severity === 'MEDIUM' ? 'var(--warning)' : 'var(--info)'
                }`,
                animation: i === 0 ? 'highlightNew 2s ease-out' : 'none',
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
                    {finding.summary?.slice(0, 150)}{finding.summary?.length > 150 ? '…' : ''}
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginTop: 6,
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--text-muted)',
                  }}>
                    <span>{((finding.confidence || 0) * 100).toFixed(0)}%</span>
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
      )}

      {activeView === 'audit' && (
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Audit Trail
          </div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-xs)',
            maxHeight: 400,
            overflowY: 'auto',
          }}>
            {auditLog.map((entry, i) => (
              <div key={entry.id || i} className="glass-row-hover" style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                padding: 'var(--space-sm)',
                background: 'rgba(14, 18, 30, 0.4)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-sm)',
              }}>
                <Badge size="xs" colorScheme="muted">{entry.action}</Badge>
                <span style={{ color: 'var(--accent2)', fontWeight: 'var(--font-weight-semibold)' }}>{entry.actor}</span>
                <span style={{ color: 'var(--text-muted)', flex: 1, fontSize: 'var(--font-size-xs)' }}>{entry.details?.slice(0, 80)}</span>
                <span style={{ color: 'var(--text-dark)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {entry.deploy_hash?.slice(0, 8)}…
                </span>
                <span style={{ color: 'var(--text-dark)', fontSize: 'var(--font-size-xs)' }}>
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {activeView === 'chart' && (
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Agent Activity Breakdown
          </div>
          {chartData.length > 0 && <AgentActivityChart data={chartData} height={200} />}
          <div style={{ marginTop: 'var(--space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
            {chartData.map((d, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                fontSize: 'var(--font-size-sm)',
              }}>
                <span style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--text)' }}>{d.agent}</span>
                <div style={{
                  flex: 1,
                  height: 6,
                  background: 'rgba(14, 18, 30, 0.4)',
                  borderRadius: 3,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${(d.count / (Math.max(...chartData.map(c => c.count)) || 1)) * 100}%`,
                    background: 'var(--gradient-accent)',
                    borderRadius: 3,
                  }} />
                </div>
                <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{d.count}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

export default LiveFeed
