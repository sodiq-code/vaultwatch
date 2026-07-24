import { useState, useEffect } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine, SkeletonTable } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'

const ACTION_COLORS = {
  scan_complete:     'accent',
  finding_written:   'success',
  risk_score_updated:'success',
  alert_dispatched:  'danger',
  self_correction:   'warning',
  rwa_assessed:      'info',
  policy_updated:    'info',
  x402_payment:      'warning',
  behavior_indexed:  'accent',
  safety_blocked:    'danger',
}

const ACTION_HEX = {
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

export default function AuditPanel({ api, addToast }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [limit, setLimit] = useState(50)
  const [writeForm, setWriteForm] = useState({ action: '', actor: '', details: '' })
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
    try {
      const data = await api.writeAudit(writeForm)
      addToast({
        type: 'success',
        message: `Entry submitted — deploy hash: ${data.deploy_hash?.slice(0, 32)}… · Block #${data.block_height?.toLocaleString()} · Contract: AuditTrail`,
      })
      loadLog()
    } catch (e) {
      addToast({ type: 'error', message: `Write failed: ${e.message}` })
    } finally {
      setWriting(false)
    }
  }

  return (
    <div>
      <PageHeader
        icon="📋"
        badge="AUDIT"
        title="Audit Log"
        subtitle={
          <>
            On-chain audit trail — all agent actions recorded via AuditTrail contract on Casper Testnet.{' '}
            <a
              href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.AuditTrail}`}
              target="_blank" rel="noopener noreferrer"
              style={{ color: 'var(--accent)', fontSize: 'var(--font-size-xs)' }}
            >
              View AuditTrail deploy ↗
            </a>
          </>
        }
      />

      {/* Agent pipeline activity */}
      <GlassCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', margin: 0 }}>
            Pipeline Activity Log <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 'var(--font-weight-normal)', color: 'var(--text-muted)' }}>({entries.length} entries)</span>
          </h2>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
            <Input
              type="select"
              value={limit}
              onChange={e => setLimit(Number(e.target.value))}
              style={{ width: 120 }}
            >
              {[10, 25, 50, 100].map(n => <option key={n} value={n}>Last {n}</option>)}
            </Input>
            <GradientBtn
              variant="ghost"
              size="sm"
              onClick={loadLog}
              disabled={loading}
              loading={loading}
            >
              Refresh
            </GradientBtn>
          </div>
        </div>

        {loading && entries.length === 0 ? (
          <SkeletonTable rows={6} cols={4} />
        ) : entries.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>No audit entries.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-sm)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)', width: 40 }}>#</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Action</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Agent</th>
                  <th style={{ padding: 'var(--space-sm) var(--space-md)' }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => {
                  const actionVariant = ACTION_COLORS[e.action] || 'accent'
                  return (
                    <tr key={i} className="glass-row-hover" style={{
                      borderBottom: '1px solid var(--border)',
                      transition: 'background var(--transition-normal)',
                    }}>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>{e.id || i + 1}</td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)' }}>
                        <Badge variant={actionVariant} size="sm">{e.action}</Badge>
                      </td>
                      <td style={{ padding: 'var(--space-sm) var(--space-md)', fontWeight: 'var(--font-weight-semibold)', fontSize: 'var(--font-size-xs)' }}>{e.actor}</td>
                      <td style={{
                        padding: 'var(--space-sm) var(--space-md)', color: 'var(--text-muted)',
                        maxWidth: 320, overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        fontSize: 'var(--font-size-xs)',
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
      </GlassCard>

      {/* Write demo */}
      <GlassCard>
        <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 6 }}>Write Audit Entry</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', marginBottom: 'var(--space-md)' }}>
          Simulates AuditAgent writing to the{' '}
          <a href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.AuditTrail}`}
            target="_blank" rel="noopener noreferrer"
            style={{ color: 'var(--accent)' }}>
            AuditTrail deploy ↗
          </a>{' '}
          on Casper Testnet.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
          <Input
            label="Action"
            value={writeForm.action}
            onChange={e => setWriteForm(f => ({ ...f, action: e.target.value }))}
            placeholder="e.g. policy_update"
          />
          <Input
            label="Actor (Agent)"
            value={writeForm.actor}
            onChange={e => setWriteForm(f => ({ ...f, actor: e.target.value }))}
            placeholder="e.g. AuditAgent"
          />
        </div>
        <Input
          value={writeForm.details}
          onChange={e => setWriteForm(f => ({ ...f, details: e.target.value }))}
          placeholder="Details (optional)"
          style={{ marginBottom: 'var(--space-sm)' }}
        />
        <GradientBtn
          onClick={handleWrite}
          disabled={!writeForm.action || !writeForm.actor || writing}
          loading={writing}
        >
          {writing ? 'Submitting...' : 'Submit to AuditTrail'}
        </GradientBtn>
      </GlassCard>
    </div>
  )
}
