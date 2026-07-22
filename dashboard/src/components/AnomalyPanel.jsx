import { useState } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'
import { RiskGaugeChart } from '../charts/RiskGaugeChart.jsx'
import { AnomalyBarChart } from '../charts/AnomalyBarChart.jsx'

const DEFAULT_METRICS = {
  protocol:         'CasperSwap',
  tvl:              12_000_000,
  volume_24h:       2_400_000,
  price_change_1h:  -2.5,
  num_transactions: 340,
  liquidity_ratio:  0.65,
}

const FIELDS = [
  { key: 'protocol',         label: 'Protocol Name',       type: 'text' },
  { key: 'tvl',              label: 'TVL (USD)',            type: 'number' },
  { key: 'volume_24h',       label: '24h Volume (USD)',     type: 'number' },
  { key: 'price_change_1h',  label: 'Price Change 1h (%)', type: 'number' },
  { key: 'num_transactions', label: 'Transactions (24h)',   type: 'number' },
  { key: 'liquidity_ratio',  label: 'Liquidity Ratio (0–1)', type: 'number' },
]

// Build AnomalyBarChart data from anomaly result
function buildBarData(result) {
  if (!result?.anomalies?.length) return []
  return result.anomalies.map(a => {
    const text = typeof a === 'string' ? a : `${a.metric}: ${a.value} (threshold ${a.threshold}, ${a.severity})`
    const sev = typeof a === 'object' ? a.severity : 'MEDIUM'
    const color = sev === 'HIGH' || sev === 'CRITICAL' ? '#ef4444' : sev === 'MEDIUM' ? '#f59e0b' : '#22c55e'
    const metric = typeof a === 'object' ? a.metric : text.split(':')[0]
    const value = typeof a === 'object' ? a.value : 50
    const threshold = typeof a === 'object' ? a.threshold : null
    return { metric, value, threshold, color, unit: typeof a === 'object' ? '' : '' }
  })
}

export default function AnomalyPanel({ api, addToast }) {
  const [metrics, setMetrics] = useState(DEFAULT_METRICS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const update = (key, val) => setMetrics(m => ({ ...m, [key]: val }))

  const handleDetect = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.detectAnomaly({
        ...metrics,
        tvl:              parseFloat(metrics.tvl),
        volume_24h:       parseFloat(metrics.volume_24h),
        price_change_1h:  parseFloat(metrics.price_change_1h),
        num_transactions: parseInt(metrics.num_transactions),
        liquidity_ratio:  parseFloat(metrics.liquidity_ratio),
      })
      setResult(data)
      addToast({ type: 'success', message: 'Anomaly detection completed' })
    } catch (e) {
      setError(e.message)
      addToast({ type: 'error', message: `Anomaly detection failed: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        icon="⚡"
        badge="DETECT"
        title="Anomaly Detection"
        subtitle="AnomalyAgent (llama-3.3-70b-versatile) with SelfCorrectionAgent loop · findings written to AuditTrail + RiskOracle on Casper."
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
        {/* Input */}
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
            Protocol Metrics
          </h2>
          <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
            {FIELDS.map(field => (
              <Input
                key={field.key}
                label={field.label}
                type={field.type}
                value={metrics[field.key]}
                onChange={e => update(field.key, e.target.value)}
                step={field.type === 'number' ? 'any' : undefined}
              />
            ))}
          </div>
          <GradientBtn
            onClick={handleDetect}
            disabled={loading}
            loading={loading}
            style={{ marginTop: 'var(--space-md)', width: '100%' }}
          >
            {loading ? 'Calling AnomalyAgent via Groq...' : 'Detect Anomalies'}
          </GradientBtn>
          {error && (
            <GlassCard glow="danger" style={{ marginTop: 'var(--space-sm)', padding: 'var(--space-sm)' }}>
              <span style={{ color: 'var(--danger)', fontSize: 'var(--font-size-sm)' }}>⚠ {error}</span>
            </GlassCard>
          )}
        </GlassCard>

        {/* Result */}
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
            AnomalyAgent Result
          </h2>
          {loading && !result ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', paddingTop: 20 }}>
              <SkeletonLine width="60%" height={80} />
              <SkeletonLine width="100%" height={20} />
              <SkeletonLine width="80%" height={20} />
              <SkeletonLine width="100%" height={40} />
            </div>
          ) : result ? (
            <>
              {/* RiskGaugeChart replaces manual RiskGauge */}
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--space-md)' }}>
                <RiskGaugeChart score={Math.round(result.risk_score ?? 0)} size={160} />
              </div>

              {/* AnomalyBarChart for metric visualization */}
              {result.anomalies && result.anomalies.length > 0 && (
                <div style={{ marginBottom: 'var(--space-md)' }}>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 'var(--space-sm)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    Detected Anomalies
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 'var(--space-sm)' }}>
                    {result.anomalies.map((a, i) => {
                      const text = typeof a === 'string'
                        ? a
                        : `${a.metric}: ${a.value} (threshold ${a.threshold}, ${a.severity})`
                      const sev = typeof a === 'object' ? a.severity : 'MEDIUM'
                      return <Badge key={i} variant={sev === 'HIGH' || sev === 'CRITICAL' ? 'danger' : sev === 'MEDIUM' ? 'warning' : 'success'} size="sm">{text}</Badge>
                    })}
                  </div>
                  <AnomalyBarChart metrics={buildBarData(result)} height={160} />
                </div>
              )}

              {(!result.anomalies || result.anomalies.length === 0) && (
                <GlassCard glow="success" style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                  <span style={{ color: 'var(--success)', fontSize: 'var(--font-size-sm)' }}>
                    ✓ No anomalies detected
                  </span>
                </GlassCard>
              )}

              {result.recommendation && (
                <GlassCard style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                  <strong style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Recommendation</strong>
                  <p style={{ marginTop: 4, lineHeight: 1.5, fontSize: 'var(--font-size-sm)' }}>{result.recommendation}</p>
                </GlassCard>
              )}

              {result.self_correction_applied && (
                <Badge variant="info" size="md" style={{ marginBottom: 'var(--space-sm)', display: 'inline-flex' }}>
                  ⟳ SelfCorrectionAgent applied — confidence re-evaluated
                </Badge>
              )}

              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {result.confidence !== undefined && (
                  <span>Confidence: <strong style={{ color: 'var(--text)' }}>
                    <AnimatedCounter value={result.confidence * 100} formatter={v => `${Math.round(v)}%`} />
                  </strong></span>
                )}
                {result.agent && <span>Agent: {result.agent}</span>}
                {result._source && <span>Data source: <SourceBadge source={result._source} /></span>}
                {result.on_chain_contract && (
                  <span>
                    On-chain:{' '}
                    <a
                      href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.SentinelAlertLog}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--accent)', fontFamily: 'var(--font)' }}
                    >
                      AuditTrail deploy ↗
                    </a>
                  </span>
                )}
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 'var(--font-size-sm)' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>⚠</div>
              Enter protocol metrics and click detect<br />
              <span style={{ fontSize: 'var(--font-size-xs)' }}>Real Groq AI · llama-3.3-70b-versatile</span>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
