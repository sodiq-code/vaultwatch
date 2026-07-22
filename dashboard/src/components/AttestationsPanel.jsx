/**
 * AttestationsPanel — EAS-style attestation viewer showing schema, attester,
 * dataHash, verification proof, on-chain status for each attestation.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'
import { CONTRACT_HASHES } from '../liveApi.js'

const DATA_TYPE_ICONS = {
  risk_finding: '⚡',
  rwa_assessment: '📊',
  anomaly_detection: '🔍',
  audit_record: '📋',
  x402_payment: '💰',
}

const DATA_TYPE_COLORS = {
  risk_finding: 'var(--accent)',
  rwa_assessment: 'var(--accent2)',
  anomaly_detection: 'var(--warning)',
  audit_record: 'var(--success)',
  x402_payment: 'var(--info)',
}

export function AttestationsPanel({ api, addToast }) {
  const [attestations, setAttestations] = useState([])
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState(null)
  const [selectedAtt, setSelectedAtt] = useState(null)
  const [filterType, setFilterType] = useState('all')

  useEffect(() => {
    loadAttestations()
    const interval = setInterval(loadAttestations, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadAttestations = async () => {
    try {
      const data = await api.getAttestations()
      if (data) {
        setAttestations(data.attestations || data || [])
        setSource(data._source || 'fallback')
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

  const filteredAtts = filterType === 'all'
    ? attestations
    : attestations.filter(a => a.dataType === filterType)

  const typeCounts = attestations.reduce((acc, a) => {
    acc[a.dataType || 'unknown'] = (acc[a.dataType || 'unknown'] || 0) + 1
    return acc
  }, {})

  const onChainCount = attestations.filter(a => a.onChain).length

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Attestations"
        subtitle="EAS-style on-chain attestation records — schema, attester, proof"
        icon="📋"
        source={source}
        actions={
          <GradientBtn variant="ghost" size="sm" onClick={loadAttestations} icon="⟳">
            Refresh
          </GradientBtn>
        }
      />

      {/* Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="Total Attestations" value={attestations.length} icon="📋" color="var(--accent)" />
        <StatCard label="On-Chain" value={onChainCount} icon="🔗" color="var(--success)" />
        <StatCard label="Verified" value={attestations.filter(a => a.status === 'verified').length} icon="✓" color="var(--accent2)" />
        <StatCard label="Schemas" value={Object.keys(typeCounts).length} icon="📄" color="var(--warning)" />
      </div>

      {/* Filter tabs */}
      <div style={{
        display: 'flex',
        gap: 'var(--space-sm)',
        marginBottom: 'var(--space-lg)',
        overflowX: 'auto',
      }}>
        <GradientBtn variant={filterType === 'all' ? 'primary' : 'ghost'} size="sm" onClick={() => setFilterType('all')}>
          All ({attestations.length})
        </GradientBtn>
        {Object.entries(DATA_TYPE_ICONS).map(([type, icon]) => (
          <GradientBtn
            key={type}
            variant={filterType === type ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setFilterType(type)}
          >
            {icon} {type.replace('_', ' ')} ({typeCounts[type] || 0})
          </GradientBtn>
        ))}
      </div>

      {/* Attestation cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: 'var(--space-md)',
      }}>
        {filteredAtts.map((att, i) => {
          const icon = DATA_TYPE_ICONS[att.dataType] || '📋'
          const color = DATA_TYPE_COLORS[att.dataType] || 'var(--accent)'
          const isSelected = selectedAtt?.id === att.id

          return (
            <GlassCard
              key={att.id || i}
              animated
              className={`stagger-${Math.min(i + 1, 6)}`}
              glow={isSelected}
              glowColor="cyan"
              onClick={() => setSelectedAtt(isSelected ? null : att)}
              style={{ padding: 'var(--space-lg)', cursor: 'pointer' }}
            >
              {/* Header */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 'var(--space-md)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                  <span style={{ fontSize: 18 }}>{icon}</span>
                  <Badge size="sm" colorScheme={att.dataType === 'risk_finding' ? 'accent' : att.dataType === 'rwa_assessment' ? 'violet' : att.dataType === 'anomaly_detection' ? 'warning' : 'success'}>
                    {att.dataType?.replace('_', ' ')}
                  </Badge>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {att.onChain && <Badge size="xs" colorScheme="success" icon="🔗">on-chain</Badge>}
                  <Badge size="xs" colorScheme={att.status === 'verified' ? 'success' : 'muted'}>{att.status}</Badge>
                </div>
              </div>

              {/* Schema */}
              <div style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: color,
                marginBottom: 'var(--space-sm)',
                fontFamily: 'var(--font-mono)',
                wordBreak: 'break-all',
              }}>
                Schema: {att.schemaId}
              </div>

              {/* Attester */}
              <div style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-xs)',
              }}>
                <span style={{ color: 'var(--text-muted)' }}>Attester:</span> {att.attester}
              </div>

              {/* Recipient */}
              <div style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-xs)',
              }}>
                <span style={{ color: 'var(--text-muted)' }}>Recipient:</span> {att.recipient}
              </div>

              {/* Data hash */}
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                marginBottom: 'var(--space-xs)',
                wordBreak: 'break-all',
              }}>
                DataHash: {att.dataHash}
              </div>

              {/* Verification proof */}
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--accent)',
                marginBottom: 'var(--space-xs)',
              }}>
                <span style={{ color: 'var(--text-muted)' }}>Proof:</span> {att.verificationProof}
              </div>

              {/* Deploy hash */}
              {att.deployHash && (
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  marginBottom: 'var(--space-xs)',
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>Deploy:</span> {att.deployHash?.slice(0, 16)}…{att.deployHash?.slice(-8)}
                </div>
              )}

              {/* Timestamp */}
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-dark)',
                textAlign: 'right',
              }}>
                {new Date(att.timestamp).toLocaleString()}
              </div>
            </GlassCard>
          )
        })}
      </div>

      {filteredAtts.length === 0 && (
        <GlassCard hover={false} style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
            No attestations found for this filter
          </div>
        </GlassCard>
      )}

      {/* Selected attestation detail */}
      {selectedAtt && (
        <GlassCard hover={false} glow glowColor="cyan" style={{
          padding: 'var(--space-lg)',
          marginTop: 'var(--space-lg)',
        }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--accent)',
            marginBottom: 'var(--space-md)',
          }}>
            Attestation Detail — {selectedAtt.id}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
            {Object.entries(selectedAtt).map(([key, value]) => (
              <div key={key} style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--text-secondary)',
                wordBreak: 'break-all',
              }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 'var(--font-weight-medium)' }}>{key}:</span>
                <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 6 }}>{String(value)}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

export default AttestationsPanel
