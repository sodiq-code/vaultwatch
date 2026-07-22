import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

/**
 * CSPR/USD price chart — 7-day area chart with gradient fill.
 * Uses real data from fetchCSPRPriceHistory with mock fallback.
 */
const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="glass-card-static" style={{ padding: 'var(--space-sm) var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
        {new Date(d.ts).toLocaleDateString()}
      </div>
      <div style={{ color: 'var(--success)', fontWeight: 'var(--font-weight-semibold)' }}>
        ${d.price?.toFixed(4)}
      </div>
    </div>
  )
}

export function CSPRPriceChart({ data = [], height = 120 }) {
  if (!data.length) {
    return <div className="skeleton-shimmer" style={{ height, borderRadius: 'var(--radius-md)' }} />
  }

  const isUp = data.length > 1 && data[data.length - 1].price >= data[0].price
  const color = isUp ? '#22c55e' : '#ef4444'

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis dataKey="ts" hide />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10, fill: '#7b8ba8' }} tickCount={3} />
        <Tooltip content={<CustomTooltip />} />
        <Area type="monotone" dataKey="price" stroke={color} strokeWidth={2} fill="url(#priceGrad)" animationDuration={600} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export default CSPRPriceChart
