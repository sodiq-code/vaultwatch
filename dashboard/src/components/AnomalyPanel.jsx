/**
 * AnomalyPanel — Enhanced anomaly detection with gauge chart, metrics visualization,
 * and self-correction status.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SeverityBadge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'
import { RiskGaugeChart } from '../charts/RiskGaugeChart.jsx'
import { AnomalyBarChart } from '../charts/AnomalyBarChart.jsx'

const DEFAULT_METRICS = {
  protocol: 'CasperSwap',
  price_change_1h: 2.5,
  volume_24h: 5000,
  liquidity_ratio: 0.65,
  tvl_change_24h: -5,
  whale_activity: 0.12,
}

export function AnomalyPanel({ api, addToast }) {
  const [metrics, setMetrics] = useState(DEFAULT_METRICS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState(null)

  const handleDetect = async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await api.detectAnomaly(metrics)
      setResult(res)
      setSource(res._source || 'fallback')
      addToast({ type: res.risk_score > 70 ? 'error' : 'info', message: `Anomaly detection: risk score ${res.risk_score}` })
    } catch (e) {
      addToast({ type: 'error', message: `Anomaly detection failed: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  // Prepare bar chart data from anomalies
  const anomalyChartData = result?.anomalies?.map(a => ({
    metric: a.metric,
    value: typeof a.value === 'number' ? a.value : Number(a.value) || 0,
    threshold: a.threshold || 0,
    severity: a.severity,
    color: a.severity === 'CRITICAL' ? '#ef4444' : a.severity === 'HIGH' ? '#ff6b7a' : a.severity === 'MEDIUM' ? '#f59e0b' : '#22c55e',
  })) || []

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="Anomaly Detection"
        subtitle="Real-time anomaly detection with self-correction pipeline"
        icon="⚡"
        source={source}
      />

      {/* Stats */}
      {result && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
          gap: 'var(--space-md)',
          marginBottom: 'var(--space-lg)',
        }}>
          <StatCard label="Risk Score" value={result.risk_score} suffix="/100" icon="⚡" color={result.risk_score > 70 ? 'var(--danger)' : result.risk_score > 40 ? 'var(--warning)' : 'var(--success)'} />
          <StatCard label="Anomalies" value={result.anomalies?.length || 0} icon="🔍" color="var(--accent2)" />
          <StatCard label="Confidence" value={((result.confidence || 0) * 100).toFixed(1)} suffix="%" icon="📊" color="var(--accent)" />
          <StatCard label="Self-Corrected" value={result.self_correction_applied ? 'Yes' : 'No'} icon="⟳" color={result.self_correction_applied ? 'var(--success)' : 'var(--text-muted)'} />
        </div>
      )}

      {/* Two column layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        marginBottom: 'var(--space-lg)',
      }}>
        {/* Input metrics panel */}
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Detection Parameters
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <Input label="Protocol" value={metrics.protocol} onChange={(v) => setMetrics(prev => ({ ...prev, protocol: v }))} icon="🔗" clearable />
            <Input label="Price Change 1h (%)" value={String(metrics.price_change_1h)} onChange={(v) => setMetrics(prev => ({ ...prev, price_change_1h: Number(v) || 0 }))} icon="📈" mono />
            <Input label="Volume 24h" value={String(metrics.volume_24h)} onChange={(v) => setMetrics(prev => ({ ...prev, volume_24h: Number(v) || 0 }))} icon="📊" mono />
            <Input label="Liquidity Ratio" value={String(metrics.liquidity_ratio)} onChange={(v) => setMetrics(prev => ({ ...prev, liquidity_ratio: Number(v) || 0 }))} icon="💧" mono />
            <Input label="TVL Change 24h (%)" value={String(metrics.tvl_change_24h)} onChange={(v) => setMetrics(prev => ({ ...prev, tvl_change_24h: Number(v) || 0 }))} icon="📉" mono />
            <Input label="Whale Activity" value={String(metrics.whale_activity)} onChange={(v) => setMetrics(prev => ({ ...prev, whale_activity: Number(v) || 0 }))} icon="🐋" mono />
          </div>

          <GradientBtn
            variant="primary"
            onClick={handleDetect}
            loading={loading}
            fullWidth
            style={{ marginTop: 'var(--space-lg)' }}
            icon="⚡"
          >
            Detect Anomalies
          </GradientBtn>
        </GlassCard>

        {/* Results panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          <GlassCard hover={false} style={{
            padding: 'var(--space-lg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {result ? (
              <RiskGaugeChart score={result.risk_score} size={200} />
            ) : (
              <div style={{
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: 'var(--font-size-sm)',
              }}>
                <div style={{ fontSize: 40, marginBottom: 8 }}>⚡</div>
                Run detection to see results
              </div>
            )}
          </GlassCard>

          {/* Recommendation */}
          {result && (
            <GlassCard hover={false} style={{ padding: 'var(--space-md)' }}>
              <div style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-sm)',
              }}>
                Recommendation
              </div>
              <div style={{
                fontSize: 'var(--font-size-md)',
                color: result.risk_score > 70 ? 'var(--danger)' : result.risk_score > 40 ? 'var(--warning)' : 'var(--success)',
                fontWeight: 'var(--font-weight-semibold)',
              }}>
                {result.recommendation}
              </div>
              {result.self_correction_applied && (
                <div style={{
                  marginTop: 'var(--space-sm)',
                  padding: '6px 10px',
                  background: 'rgba(0, 230, 138, 0.1)',
                  border: '1px solid rgba(0, 230, 138, 0.25)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--success)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}>
                  ⟳ Self-correction applied — initial score adjusted
                </div>
              )}
              <SourceBadge source={source} style={{ marginTop: 'var(--space-sm)' }} />
            </GlassCard>
          )}

          {/* Anomaly bar chart */}
          {anomalyChartData.length > 0 && (
            <GlassCard hover={false} style={{ padding: 'var(--space-md)' }}>
              <div style={{
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-sm)',
              }}>
                Anomaly Metrics vs Thresholds
              </div>
              <AnomalyBarChart metrics={anomalyChartData} height={180} />
            </GlassCard>
          )}
        </div>
      </div>

      {/* Anomaly detail list */}
      {result?.anomalies?.length > 0 && (
        <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
          <div style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            color: 'var(--text)',
            marginBottom: 'var(--space-md)',
          }}>
            Detected Anomalies
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {result.anomalies.map((anomaly, i) => (
              <div key={i} className="slide-up" style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-md)',
                padding: 'var(--space-md)',
                background: anomaly.severity === 'CRITICAL' ? 'rgba(255, 59, 92, 0.06)' : 'rgba(14, 18, 30, 0.4)',
                borderRadius: 'var(--radius-md)',
                borderLeft: `3px solid ${anomaly.severity === 'CRITICAL' ? 'var(--danger)' : anomaly.severity === 'HIGH' ? '#ff6b7a' : 'var(--warning)'}`,
              }}>
                <SeverityBadge severity={anomaly.severity} />
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 'var(--font-size-md)',
                    fontWeight: 'var(--font-weight-semibold)',
                    color: 'var(--text)',
                  }}>
                    {anomaly.metric}
                  </div>
                  <div style={{
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--text-secondary)',
                    marginTop: 2,
                  }}>
                    Value: {anomaly.value} — Threshold: {anomaly.threshold}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

export default AnomalyPanel
