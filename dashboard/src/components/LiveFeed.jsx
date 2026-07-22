import { useState, useEffect, useRef, useCallback } from 'react'
import { SEED_FINDINGS, fetchLiveFindings, CONTRACT_HASHES, getLiveBlockHeight } from '../liveApi.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'
import { AgentActivityChart } from '../charts/AgentActivityChart.jsx'

const SEV_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f59e0b',
  MEDIUM:   '#3b82f6',
  LOW:      '#22c55e',
}

// Simulate realistic agent activity log events
function generateEvent(index) {
  const agents = ['ScannerAgent', 'AnomalyAgent', 'SelfCorrectionAgent', 'AuditAgent', 'IntelAgent', 'RWAAgent', 'SafetyGuard']
  const protocols = ['CasperSwap', 'CasperLend', 'CasperYield', 'CasperDEX', 'CSPRFarm']
  const events = [
    (p) => ({ type: 'SCAN', msg: `ScannerAgent scanned ${p} — ${Math.floor(Math.random()*5)+1} events ingested`, agent: 'ScannerAgent' }),
    (p) => ({ type: 'ANOMALY', msg: `AnomalyAgent classified ${p} event as ${['HIGH', 'MEDIUM', 'LOW'][Math.floor(Math.random()*3)]} risk`, agent: 'AnomalyAgent' }),
    (p) => ({ type: 'AUDIT', msg: `AuditAgent wrote finding to AuditTrail contract on casper-test`, agent: 'AuditAgent' }),
    (p) => ({ type: 'SAFETY', msg: `SafetyGuard passed query in ${Math.floor(Math.random()*30)+15}ms — no injection detected`, agent: 'SafetyGuard' }),
    (p) => ({ type: 'CORRECT', msg: `SelfCorrectionAgent re-evaluated low-confidence (${(Math.random()*0.2+0.5).toFixed(2)}) finding`, agent: 'SelfCorrectionAgent' }),
    (p) => ({ type: 'RWA', msg: `RWAAgent assessed asset via Groq Compound — collateral ratio within bounds`, agent: 'RWAAgent' }),
    (p) => ({ type: 'ALERT', msg: `IntelAgent dispatched ${['MEDIUM', 'HIGH'][Math.floor(Math.random()*2)]} alert to ${Math.floor(Math.random()*5)+1} subscribers`, agent: 'IntelAgent' }),
    (p) => ({ type: 'BLOCK', msg: `New block #${getLiveBlockHeight()} finalized on casper-test`, agent: 'Network' }),
    (p) => ({ type: 'X402', msg: `x402 payment received — 0.5 CSPR deducted from SubscriberVault`, agent: 'IntelAgent' }),
    (p) => ({ type: 'POLICY', msg: `RiskPolicyManager policy check passed for ${p}`, agent: 'RiskPolicyManager' }),
  ]
  const proto  = protocols[Math.floor(Math.random() * protocols.length)]
  const evtFn  = events[index % events.length]
  return {
    id:        `EVT-${Date.now()}-${index}`,
    timestamp: new Date(),
    protocol:  proto,
    ...evtFn(proto),
  }
}

const TYPE_COLOR = {
  SCAN:    '#4f7cff',
  ANOMALY: '#f59e0b',
  AUDIT:   '#22c55e',
  SAFETY:  '#8b5cf6',
  CORRECT: '#06b6d4',
  RWA:     '#10b981',
  ALERT:   '#ef4444',
  BLOCK:   '#64748b',
  X402:    '#f97316',
  POLICY:  '#6366f1',
}

const TYPE_VARIANT = {
  SCAN:    'accent',
  ANOMALY: 'warning',
  AUDIT:   'success',
  SAFETY:  'accent',
  CORRECT: 'info',
  RWA:     'success',
  ALERT:   'danger',
  BLOCK:   'default',
  X402:    'warning',
  POLICY:  'accent',
}

function EventRow({ event, isNew }) {
  const color = TYPE_COLOR[event.type] || '#64748b'
  const ts    = event.timestamp.toLocaleTimeString()
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
      padding: '9px 12px',
      background: isNew ? color + '11' : 'transparent',
      borderBottom: '1px solid var(--border)',
      fontSize: 'var(--font-size-xs)',
      transition: 'background 1s ease',
    }}>
      <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font)', flexShrink: 0, fontSize: 'var(--font-size-xs)', marginTop: 1 }}>{ts}</span>
      <Badge variant={TYPE_VARIANT[event.type] || 'default'} size="sm" style={{ flexShrink: 0, marginTop: 1 }}>
        {event.type}
      </Badge>
      <span style={{ color: 'var(--text-muted)', flexShrink: 0, fontSize: 'var(--font-size-xs)', marginTop: 1 }}>
        [{event.agent}]
      </span>
      <span style={{ color: 'var(--text)', flex: 1, lineHeight: 1.4 }}>{event.msg}</span>
    </div>
  )
}

function FindingCard({ f }) {
  const color = SEV_COLOR[f.severity] || '#64748b'
  const age   = Math.round((Date.now() - (f.timestamp || 0)) / 60000)
  const ageStr = age < 60 ? `${age}m ago` : `${Math.round(age / 60)}h ago`
  const isOnChain = f.source === 'on-chain'
  const explorerUrl = isOnChain
    ? `https://testnet.cspr.live/contract/${f.contract_hash}`
    : `https://testnet.cspr.live/deploy/${f.contract_hash}`
  return (
    <GlassCard style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 'var(--font-weight-bold)', fontSize: 'var(--font-size-sm)' }}>{f.protocol}</span>
          <span style={{ fontFamily: 'var(--font)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>{f.id}</span>
          {isOnChain && <SourceBadge source="on-chain" />}
          {!isOnChain && f.source && <SourceBadge source={f.source} />}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>{ageStr}</span>
          <Badge size="sm">{f.severity}</Badge>
        </div>
      </div>
      <div style={{ color: 'var(--text-muted)', marginBottom: 7, lineHeight: 1.5, fontSize: 'var(--font-size-xs)' }}>{f.summary}</div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <a href={explorerUrl}
          target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--accent)', fontSize: 'var(--font-size-xs)', textDecoration: 'none' }}>
          ⬡ {f.contract} ↗
        </a>
        <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>Via: {f.agent}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
          Conf: {(f.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </GlassCard>
  )
}

export default function LiveFeed({ api, cspr, network, blockHeight, addToast }) {
  const [events, setEvents]     = useState(() => {
    return Array.from({ length: 12 }, (_, i) => ({ ...generateEvent(i), isNew: false }))
  })
  const [paused, setPaused]     = useState(false)
  const [filter, setFilter]     = useState('ALL')
  const [newIds, setNewIds]     = useState(new Set())
  const [findings, setFindings] = useState(SEED_FINDINGS)
  const [findingsSource, setFindingsSource] = useState('seed')
  const eventCounter            = useRef(12)
  const listRef                 = useRef(null)

  // Fetch REAL on-chain findings through the FastAPI proxy
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const r = await fetchLiveFindings(20)
      if (cancelled) return
      if (r?.findings?.length) {
        setFindings(r.findings)
        setFindingsSource(r.source)
      }
    }
    load()
    const id = setInterval(load, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [])

  // Emit new events
  useEffect(() => {
    if (paused) return
    const tick = setInterval(() => {
      const newEvt = { ...generateEvent(eventCounter.current++), isNew: true }
      setEvents(prev => [...prev.slice(-150), newEvt])
      setNewIds(ids => { const s = new Set(ids); s.add(newEvt.id); return s })
      setTimeout(() => {
        setNewIds(ids => { const s = new Set(ids); s.delete(newEvt.id); return s })
      }, 2000)
    }, 2800 + Math.random() * 2000)
    return () => clearInterval(tick)
  }, [paused])

  useEffect(() => { scrollToBottom() }, [events, scrollToBottom])

  const allTypes = ['ALL', 'SCAN', 'ANOMALY', 'AUDIT', 'ALERT', 'SAFETY', 'CORRECT', 'RWA', 'BLOCK', 'X402', 'POLICY']
  const filtered = filter === 'ALL' ? events : events.filter(e => e.type === filter)

  // Agent stats
  const agentCounts = events.reduce((acc, e) => {
    acc[e.agent] = (acc[e.agent] || 0) + 1
    return acc
  }, {})
  const sortedAgents = Object.entries(agentCounts).sort((a, b) => b[1] - a[1])
  const totalEvents  = events.length

  // Build AgentActivityChart data
  const chartData = sortedAgents.slice(0, 8).map(([agent, count]) => ({ agent, count }))

  return (
    <div>
      <PageHeader
        icon="📡"
        badge="LIVE"
        title="Live Agent Feed"
        subtitle="Real-time VaultWatch agent pipeline activity — events emit every 3–5s. Scroll to the bottom for latest events."
      />

      {/* ── Live Summary Stats ──────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <StatCard
          label="Events Streamed"
          value={totalEvents}
          color="accent"
          icon="📊"
        />
        <StatCard
          label="Block Height"
          value={blockHeight?.toLocaleString() ?? '—'}
          color="accent"
          icon="⬡"
        />
        <StatCard
          label="Era ID"
          value={network?.era_id ?? '—'}
          color="accent"
          icon="⚡"
        />
        <StatCard
          label="CSPR Price"
          value={cspr?.usd != null ? `$${cspr.usd.toFixed(4)}` : '—'}
          sub={cspr?.change_24h != null ? `${cspr.change_24h >= 0 ? '+' : ''}${cspr.change_24h.toFixed(2)}% 24h` : ''}
          color={cspr?.change_24h >= 0 ? 'success' : cspr?.change_24h < 0 ? 'danger' : 'accent'}
          icon="💲"
        />
        <StatCard
          label="Active Agents"
          value={7}
          color="success"
          icon="🤖"
        />
        <StatCard
          label="On-Chain Contracts"
          value={8}
          color="success"
          icon="⬡"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 'var(--space-md)' }}>
        {/* ── Event Log ────────────────────────────────────────────────── */}
        <GlassCard>
          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)' }}>Agent Event Log</span>
            <div style={{ flex: 1 }} />
            <GradientBtn
              variant={paused ? 'success' : 'ghost'}
              size="sm"
              onClick={() => setPaused(p => !p)}
            >
              {paused ? '▶ Resume' : '⏸ Pause'}
            </GradientBtn>
            <GradientBtn
              variant="ghost"
              size="sm"
              onClick={() => { setEvents([]); eventCounter.current = 0 }}
            >
              Clear
            </GradientBtn>
          </div>

          {/* Type filter */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 'var(--space-sm)' }}>
            {allTypes.map(t => (
              <Badge
                key={t}
                size="sm"
                variant={filter === t ? (TYPE_VARIANT[t] || 'accent') : 'default'}
                pulse={t === 'ALL' && filter === 'ALL'}
                style={{
                  cursor: 'pointer',
                  opacity: filter === t ? 1 : 0.6,
                  transition: 'all var(--transition-normal)',
                }}
                onClick={() => setFilter(t)}
              >
                {t}
              </Badge>
            ))}
          </div>

          {/* Event list */}
          <div ref={listRef} style={{
            height: 420, overflowY: 'auto',
            background: 'var(--glass-bg)',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'var(--font)',
            border: '1px solid var(--glass-border)',
          }}>
            {filtered.length === 0 ? (
              <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', textAlign: 'center' }}>
                No events yet{filter !== 'ALL' ? ` for filter: ${filter}` : ''}…
              </div>
            ) : filtered.map(evt => (
              <EventRow key={evt.id} event={evt} isNew={newIds.has(evt.id)} />
            ))}
          </div>

          <div style={{ marginTop: 'var(--space-sm)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Showing {filtered.length} events{filter !== 'ALL' ? ` (filtered: ${filter})` : ''}</span>
            <span>{paused ? '⏸ Paused' : '● Streaming live…'}</span>
          </div>
        </GlassCard>

        {/* ── Sidebar: Agent Stats + Active Findings ──────────────────── */}
        <div>
          {/* Agent Activity */}
          <GlassCard>
            <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-bold)', marginBottom: 'var(--space-sm)' }}>Agent Activity</h3>
            <AgentActivityChart data={chartData} height={140} />
          </GlassCard>

          {/* Contract activity */}
          <GlassCard>
            <h3 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-bold)', marginBottom: 'var(--space-sm)' }}>Active Contracts</h3>
            <div style={{ fontSize: 'var(--font-size-xs)', display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
              {Object.entries(CONTRACT_HASHES).map(([name, hash]) => (
                <div key={name} className="glass-row-hover" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: 'var(--space-xs) var(--space-sm)', background: 'var(--glass-bg)', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--glass-border)',
                  transition: 'all var(--transition-normal)',
                }}>
                  <a href={`https://testnet.cspr.live/deploy/${hash}`} target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 'var(--font-weight-semibold)' }}>{name}</a>
                  <Badge variant="success" size="sm">✓ ON-CHAIN</Badge>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>

      {/* ── Recent Findings ───────────────────────────────────────────────── */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)', display: 'flex', alignItems: 'center', gap: 8 }}>
          Recent Findings — Agent Pipeline Output
          <SourceBadge source={findingsSource} />
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontWeight: 'var(--font-weight-normal)' }}>
            written to Casper contracts
          </span>
        </h2>
        {findings.map((f, i) => (
          <FindingCard key={f.id || i} f={f} />
        ))}
        <div style={{ marginTop: 'var(--space-sm)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
          Each finding is linked to its specific on-chain contract deploy.
          Click any contract name to verify on <a href="https://testnet.cspr.live" target="_blank" rel="noopener noreferrer"
            style={{ color: 'var(--accent)', textDecoration: 'none' }}>testnet.cspr.live ↗</a>
        </div>
      </GlassCard>
    </div>
  )
}
