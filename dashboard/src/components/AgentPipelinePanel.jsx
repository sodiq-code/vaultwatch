/**
 * AgentPipelinePanel — Visual pipeline flow showing all 7 agents
 * (Scanner → Anomaly → SelfCorrection → RWA → Audit → SafetyGuard → Intel)
 * with live status, latency, findings count, and pipeline step visualization.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SourceBadge, HexBadge } from '../ui/Badge.jsx'
import { SkeletonBlock, SkeletonLine } from '../ui/Skeleton.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'

const AGENT_ICONS = {
  scanner: '🔍',
  anomaly: '⚡',
  selfcorrect: '⟳',
  rwa: '📊',
  audit: '📋',
  safety: '🛡️',
  intel: '🧠',
}

const STATUS_COLORS = {
  active: 'var(--success)',
  idle: 'var(--text-muted)',
  error: 'var(--danger)',
  paused: 'var(--warning)',
}

export function AgentPipelinePanel({ api, addToast }) {
  const [pipeline, setPipeline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(null)

  useEffect(() => {
    loadPipeline()
    const interval = setInterval(loadPipeline, 15000)
    return () => clearInterval(interval)
  }, [])

  const loadPipeline = async () => {
    try {
      const data = await api.getAgentPipeline()
      if (data) {
        setPipeline(data)
        setError(null)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 'var(--space-md)' }}>
          {Array.from({ length: 7 }, (_, i) => <SkeletonBlock key={i} height={160} />)}
        </div>
      </div>
    )
  }

  if (error && !pipeline) {
    return (
      <GlassCard hover={false} style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
        <div style={{ color: 'var(--danger)', fontSize: 'var(--font-size-lg)', marginBottom: 8 }}>Pipeline Unavailable</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>{error}</div>
      </GlassCard>
    )
  }

  const agents = pipeline?.agents || []
  const steps = pipeline?.pipelineSteps || []
  const totalRuns = pipeline?.totalRuns || 0
  const totalFindings = pipeline?.totalFindings || 0
  const source = pipeline?._source || 'fallback'

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Agent Pipeline"
        subtitle="7-agent intelligence pipeline — live processing flow"
        icon="⚡"
        source={source}
      />

      {/* Summary stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="Total Runs" value={totalRuns} icon="▶" color="var(--accent)" source={source} />
        <StatCard label="Total Findings" value={totalFindings} icon="🔍" color="var(--accent2)" source={source} />
        <StatCard label="Active Agents" value={agents.filter(a => a.status === 'active').length} icon="✓" color="var(--success)" />
        <StatCard label="Avg Latency" value={agents.length ? Math.round(agents.reduce((s, a) => s + a.avgLatency, 0) / agents.length) : 0} suffix="ms" icon="⏱" color="var(--warning)" />
      </div>

      {/* Pipeline flow visualization */}
      <GlassCard hover={false} style={{ padding: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{
          fontSize: 'var(--font-size-sm)',
          fontWeight: 'var(--font-weight-semibold)',
          color: 'var(--text-secondary)',
          marginBottom: 'var(--space-md)',
        }}>
          Pipeline Data Flow
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--space-sm)',
          overflowX: 'auto',
          padding: 'var(--space-sm) 0',
        }}>
          {agents.map((agent, i) => (
            <div key={agent.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
              {/* Agent node */}
              <div
                onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  padding: '10px 12px',
                  background: selectedAgent === agent.id
                    ? 'rgba(0, 212, 255, 0.12)'
                    : 'rgba(14, 18, 30, 0.6)',
                  border: `1px solid ${selectedAgent === agent.id ? 'var(--border3)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                  minWidth: 90,
                }}
              >
                <div style={{ fontSize: '20px' }}>{AGENT_ICONS[agent.id] || '⚙'}</div>
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: STATUS_COLORS[agent.status] || 'var(--text-muted)',
                  whiteSpace: 'nowrap',
                }}>
                  {agent.name.replace('Agent', '')}
                </div>
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {agent.avgLatency}ms
                </div>
                {agent.findings > 0 && (
                  <Badge size="xs" colorScheme={agent.findings > 10 ? 'danger' : 'accent'}>
                    {agent.findings}
                  </Badge>
                )}
              </div>
              {/* Arrow connector */}
              {i < agents.length - 1 && (
                <div style={{
                  color: 'var(--accent)',
                  fontSize: 'var(--font-size-lg)',
                  opacity: 0.5,
                  animation: 'pulse 2s ease-in-out infinite',
                }}>
                  →
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Pipeline steps detail */}
        {steps.length > 0 && (
          <div style={{ marginTop: 'var(--space-md)' }}>
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-muted)',
              marginBottom: 'var(--space-sm)',
              fontWeight: 'var(--font-weight-medium)',
            }}>
              Pipeline Steps
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
              {steps.map((step, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  padding: '6px 10px',
                  background: 'rgba(0, 212, 255, 0.04)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-secondary)',
                }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 'var(--font-weight-semibold)' }}>{step.from}</span>
                  <span style={{ color: 'var(--text-muted)' }}>→</span>
                  <span style={{ color: 'var(--accent2)', fontWeight: 'var(--font-weight-semibold)' }}>{step.to}</span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>{step.latency}ms</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </GlassCard>

      {/* Agent detail cards grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: 'var(--space-md)',
      }}>
        {agents.map((agent, i) => (
          <GlassCard key={agent.id} animated className={`stagger-${Math.min(i + 1, 6)}`} style={{ padding: 'var(--space-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
              <span style={{ fontSize: '20px' }}>{AGENT_ICONS[agent.id] || '⚙'}</span>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 'var(--font-size-md)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--text)',
                }}>
                  {agent.name}
                </div>
                <Badge size="xs" colorScheme={agent.status === 'active' ? 'success' : 'muted'} pulse={agent.status === 'active'}>
                  {agent.status}
                </Badge>
              </div>
            </div>

            {/* Metrics */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Runs</span>
                <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                  <AnimatedCounter value={agent.runs} />
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Findings</span>
                <span style={{ color: agent.findings > 10 ? 'var(--danger)' : 'var(--accent2)', fontFamily: 'var(--font-mono)' }}>
                  {agent.findings}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Avg Latency</span>
                <span style={{ color: 'var(--warning)', fontFamily: 'var(--font-mono)' }}>{agent.avgLatency}ms</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Model</span>
                <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                  {agent.model}
                </span>
              </div>
            </div>

            {/* Last run time */}
            <div style={{
              marginTop: 'var(--space-sm)',
              fontSize: 'var(--font-size-xs)',
              color: 'var(--text-dark)',
              textAlign: 'right',
            }}>
              Last: {new Date(agent.lastRun).toLocaleTimeString()}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  )
}

export default AgentPipelinePanel
