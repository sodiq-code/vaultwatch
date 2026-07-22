import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

/**
 * Agent activity bar chart — shows event counts per agent.
 * Replaces manual progress bars in LiveFeed.
 */
const AGENT_COLORS = {
  ScannerAgent: '#4f7cff',
  AnomalyAgent: '#7c5fff',
  RWAAgent: '#22c55e',
  AuditAgent: '#f59e0b',
  SafetyGuard: '#ef4444',
  IntelAgent: '#3b82f6',
  SelfCorrection: '#10b981',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card-static" style={{ padding: 'var(--space-sm) var(--space-md)', fontSize: 'var(--font-size-sm)' }}>
      <div style={{ color: 'var(--text)', fontWeight: 'var(--font-weight-semibold)' }}>{payload[0].payload.agent}</div>
      <div style={{ color: 'var(--accent)' }}>{payload[0].value} events</div>
    </div>
  )
}

export function AgentActivityChart({ data = [], height = 140 }) {
  if (!data.length) return null

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="agent" tick={{ fontSize: 10, fill: '#7b8ba8' }} interval={0} />
        <YAxis tick={{ fontSize: 10, fill: '#7b8ba8' }} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} animationDuration={600}>
          {data.map((entry, idx) => (
            <Cell key={idx} fill={AGENT_COLORS[entry.agent] || '#4f7cff'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default AgentActivityChart
