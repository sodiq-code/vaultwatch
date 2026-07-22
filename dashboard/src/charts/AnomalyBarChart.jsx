import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts'

/**
 * Anomaly metrics bar chart — compares input metrics vs thresholds.
 * Replaces static metric display in AnomalyPanel.
 */
const METRIC_COLORS = {
  safe: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="glass-card-static" style={{ padding: 'var(--space-sm) var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
      <div style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-semibold)' }}>{d.metric}</div>
      <div style={{ color: d.color }}>Value: {d.value}{d.unit || ''}</div>
      {d.threshold && <div style={{ color: 'var(--text-muted)' }}>Threshold: {d.threshold}{d.unit || ''}</div>}
    </div>
  )
}

export function AnomalyBarChart({ metrics = [], height = 180 }) {
  if (!metrics.length) return null

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={metrics} margin={{ top: 4, right: 4, left: -20, bottom: 20 }}>
        <XAxis dataKey="metric" tick={{ fontSize: 10, fill: '#7b8ba8' }} interval={0} />
        <YAxis tick={{ fontSize: 10, fill: '#7b8ba8' }} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} animationDuration={600}>
          {metrics.map((entry, idx) => (
            <Cell key={idx} fill={entry.color || METRIC_COLORS.safe} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default AnomalyBarChart
