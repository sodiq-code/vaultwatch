import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

/**
 * OTel latency chart — horizontal bars for span durations.
 * Color-coded by latency: <500ms green, 500-1500ms blue, >1500ms amber.
 * Replaces manual latency bar divs in ChainStatus.
 */
const LATENCY_COLORS = {
  fast: '#22c55e',
  normal: '#3b82f6',
  slow: '#f59e0b',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="glass-card-static" style={{ padding: 'var(--space-sm) var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
      <div style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-semibold)' }}>{d.name}</div>
      <div style={{ color: d.color }}>{d.durationMs}ms</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>{d.status}</div>
    </div>
  )
}

export function LatencyChart({ spans = [], height = 160 }) {
  if (!spans.length) return null

  const data = spans.map(s => ({
    name: s.name?.replace(/.*\./, '') || s.spanId,
    durationMs: s.durationMs || 0,
    status: s.status || 'OK',
    color: s.durationMs < 500 ? LATENCY_COLORS.fast
      : s.durationMs < 1500 ? LATENCY_COLORS.normal
      : LATENCY_COLORS.slow,
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 20, left: 60, bottom: 0 }}>
        <XAxis type="number" tick={{ fontSize: 10, fill: '#7b8ba8' }} unit="ms" />
        <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#7b8ba8' }} width={60} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="durationMs" radius={[0, 4, 4, 0]} animationDuration={600}>
          {data.map((entry, idx) => (
            <Cell key={idx} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default LatencyChart
