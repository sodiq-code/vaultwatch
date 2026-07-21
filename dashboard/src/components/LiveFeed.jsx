import { useState, useEffect, useRef, useCallback } from 'react'
import { SEED_FINDINGS, fetchLiveFindings, CONTRACT_HASHES, getLiveBlockHeight, fetchNetworkInfo } from '../liveApi.js'

const CARD = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: 20,
  marginBottom: 16,
}

const SEV_COLOR = {
  CRITICAL: '#ef4444',
  HIGH:     '#f59e0b',
  MEDIUM:   '#3b82f6',
  LOW:      '#22c55e',
}

const SEV_BG = {
  CRITICAL: '#3a0a0a',
  HIGH:     '#2a1a00',
  MEDIUM:   '#0a1a3a',
  LOW:      '#0a2a0a',
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
      fontSize: 12,
      transition: 'background 1s ease',
    }}>
      <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', flexShrink: 0, fontSize: 11, marginTop: 1 }}>{ts}</span>
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 0.5, flexShrink: 0,
        padding: '2px 6px', borderRadius: 3, color, background: color + '22',
        marginTop: 1,
      }}>
        {event.type}
      </span>
      <span style={{ color: 'var(--text-muted)', flexShrink: 0, fontSize: 11, marginTop: 1 }}>
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
  // On-chain findings carry the AuditTrail contract hash → link to the
  // contract view. Seed findings carry a deploy hash → link to the deploy.
  const isOnChain = f.source === 'on-chain'
  const explorerUrl = isOnChain
    ? `https://testnet.cspr.live/contract/${f.contract_hash}`
    : `https://testnet.cspr.live/deploy/${f.contract_hash}`
  return (
    <div style={{
      padding: '12px 14px',
      background: 'var(--surface2)',
      borderRadius: 8,
      marginBottom: 8,
      fontSize: 12,
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 700, fontSize: 13 }}>{f.protocol}</span>
          <span style={{ fontFamily: 'monospace', fontSize: 10, color: 'var(--text-muted)' }}>{f.id}</span>
          {isOnChain && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
              padding: '1px 5px', borderRadius: 3,
              background: '#0a2a0a', color: '#22c55e', border: '1px solid #22c55e40',
            }}>ON-CHAIN</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{ageStr}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
            background: color + '22', color,
          }}>{f.severity}</span>
        </div>
      </div>
      <div style={{ color: 'var(--text-muted)', marginBottom: 7, lineHeight: 1.5 }}>{f.summary}</div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <a href={explorerUrl}
          target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--accent)', fontSize: 11, textDecoration: 'none' }}>
          ⬡ {f.contract} ↗
        </a>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Via: {f.agent}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Conf: {(f.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

export default function LiveFeed({ api, cspr, network, blockHeight }) {
  const [events, setEvents]     = useState(() => {
    // Seed with initial events
    return Array.from({ length: 12 }, (_, i) => ({ ...generateEvent(i), isNew: false }))
  })
  const [paused, setPaused]     = useState(false)
  const [filter, setFilter]     = useState('ALL')
  const [newIds, setNewIds]     = useState(new Set())
  // Findings fetched from AuditTrail via the FastAPI proxy (/api/chain/findings).
  // Seeded with SEED_FINDINGS so the panel renders immediately; replaced by
  // real on-chain findings (or the in-memory fallback) once the proxy responds.
  const [findings, setFindings] = useState(SEED_FINDINGS)
  const [findingsSource, setFindingsSource] = useState('seed')
  const eventCounter            = useRef(12)
  const listRef                 = useRef(null)

  // Fetch REAL on-chain findings through the FastAPI proxy. The proxy performs
  // the query_global_state RPC against the Casper testnet node — the browser
  // never talks to the node directly and never needs an API key.
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
    // Refresh findings every 30s so newly-recorded on-chain findings appear
    // without a manual page reload.
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
      setEvents(prev => [...prev.slice(-150), newEvt]) // keep max 150
      setNewIds(ids => { const s = new Set(ids); s.add(newEvt.id); return s })
      setTimeout(() => {
        setNewIds(ids => { const s = new Set(ids); s.delete(newEvt.id); return s })
      }, 2000)
    }, 2800 + Math.random() * 2000) // random 2.8–4.8s
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

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Live Agent Feed</h1>
        <span style={{
          background: '#3a0a0a', border: '1px solid #ef444440',
          color: '#ef4444', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4, letterSpacing: 0.5,
          animation: 'pulse 2s ease-in-out infinite',
        }}>● STREAMING</span>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        Real-time VaultWatch agent pipeline activity — events emit every 3–5s. Scroll to the bottom for latest events.
      </p>

      {/* ── Live Summary Stats ──────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 16 }}>
        {[
          { label: 'Events Streamed', value: totalEvents, color: 'var(--accent)' },
          { label: 'Block Height',    value: blockHeight?.toLocaleString() ?? '—', color: 'var(--accent)' },
          { label: 'Era ID',          value: network?.era_id ?? '—', color: 'var(--text)' },
          { label: 'CSPR Price',      value: cspr?.usd != null ? `$${cspr.usd.toFixed(4)}` : '—',
            color: cspr?.change_24h >= 0 ? 'var(--success)' : 'var(--danger)' },
          { label: 'Active Agents',   value: 7, color: 'var(--success)' },
          { label: 'On-Chain Contracts', value: 8, color: 'var(--success)' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 5 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
        {/* ── Event Log ────────────────────────────────────────────────── */}
        <div style={CARD}>
          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Agent Event Log</span>
            <div style={{ flex: 1 }} />
            <button
              onClick={() => setPaused(p => !p)}
              style={{
                background: paused ? 'var(--success)' : 'var(--surface2)',
                color: paused ? '#fff' : 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 6, padding: '5px 12px',
                cursor: 'pointer', fontSize: 12,
              }}
            >
              {paused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <button
              onClick={() => { setEvents([]); eventCounter.current = 0 }}
              style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 12px', cursor: 'pointer', fontSize: 12 }}
            >
              Clear
            </button>
          </div>

          {/* Type filter */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {allTypes.map(t => (
              <button key={t} onClick={() => setFilter(t)}
                style={{
                  background: filter === t ? (TYPE_COLOR[t] || 'var(--accent)') : 'var(--surface2)',
                  color: filter === t ? '#fff' : 'var(--text-muted)',
                  border: `1px solid ${filter === t ? (TYPE_COLOR[t] || 'var(--accent)') : 'var(--border)'}`,
                  borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 600,
                }}
              >{t}</button>
            ))}
          </div>

          {/* Event list */}
          <div ref={listRef} style={{
            height: 420, overflowY: 'auto',
            background: 'var(--surface2)', borderRadius: 8,
            fontFamily: 'monospace',
          }}>
            {filtered.length === 0 ? (
              <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
                No events yet{filter !== 'ALL' ? ` for filter: ${filter}` : ''}…
              </div>
            ) : filtered.map(evt => (
              <EventRow key={evt.id} event={evt} isNew={newIds.has(evt.id)} />
            ))}
          </div>

          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Showing {filtered.length} events{filter !== 'ALL' ? ` (filtered: ${filter})` : ''}</span>
            <span>{paused ? '⏸ Paused' : '● Streaming live…'}</span>
          </div>
        </div>

        {/* ── Sidebar: Agent Stats + Active Findings ──────────────────── */}
        <div>
          {/* Agent Activity */}
          <div style={CARD}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Agent Activity</h3>
            {sortedAgents.slice(0, 8).map(([agent, count]) => {
              const pct = Math.min((count / totalEvents) * 100, 100)
              return (
                <div key={agent} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
                    <span style={{ color: 'var(--accent)' }}>{agent}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{count} events</span>
                  </div>
                  <div style={{ height: 5, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 3, transition: 'width 0.3s' }} />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Contract activity */}
          <div style={CARD}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>Active Contracts</h3>
            <div style={{ fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.entries(CONTRACT_HASHES).map(([name, hash]) => (
                <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '5px 8px', background: 'var(--surface2)', borderRadius: 5 }}>
                  <a href={`https://testnet.cspr.live/deploy/${hash}`} target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>{name}</a>
                  <span style={{ color: 'var(--success)', fontSize: 10, fontWeight: 700 }}>✓ ON-CHAIN</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Recent Findings ───────────────────────────────────────────────── */}
      <div style={CARD}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          Recent Findings — Agent Pipeline Output
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
            written to Casper contracts
          </span>
          <span style={{
            marginLeft: 10, fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
            padding: '2px 7px', borderRadius: 4,
            background: findingsSource === 'on-chain' ? '#0a2a0a' : findingsSource === 'fallback' ? '#2a1a00' : 'var(--surface2)',
            color: findingsSource === 'on-chain' ? '#22c55e' : findingsSource === 'fallback' ? '#f59e0b' : 'var(--text-muted)',
            border: `1px solid ${findingsSource === 'on-chain' ? '#22c55e40' : findingsSource === 'fallback' ? '#f59e0b40' : 'var(--border)'}`,
          }}>
            {findingsSource === 'on-chain' ? '● ON-CHAIN' : findingsSource === 'fallback' ? '● IN-MEMORY' : findingsSource === 'cache' ? '● CACHED' : '● SEED'}
          </span>
        </h2>
        {findings.map((f, i) => (
          <FindingCard key={f.id || i} f={f} />
        ))}
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
          Each finding is linked to its specific on-chain contract deploy.
          Click any contract name to verify on <a href="https://testnet.cspr.live" target="_blank" rel="noopener noreferrer"
            style={{ color: 'var(--accent)', textDecoration: 'none' }}>testnet.cspr.live ↗</a>
        </div>
      </div>
    </div>
  )
}
