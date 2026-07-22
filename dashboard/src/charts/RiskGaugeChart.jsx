import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

/**
 * Risk gauge chart — radial display of risk/anomaly score.
 * Color transitions: green → amber → red based on score.
 */
const getGaugeColor = (score) => {
  if (score >= 80) return '#ef4444'
  if (score >= 60) return '#f59e0b'
  if (score >= 40) return '#3b82f6'
  return '#22c55e'
}

export function RiskGaugeChart({ score = 0, size = 160 }) {
  const color = getGaugeColor(score)
  const gaugeData = [
    { name: 'score', value: score },
    { name: 'remaining', value: 100 - score },
  ]

  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <ResponsiveContainer width={size} height={size}>
        <PieChart>
          <Pie
            data={gaugeData}
            cx="50%"
            cy="50%"
            innerRadius={size * 0.35}
            outerRadius={size * 0.45}
            startAngle={90}
            endAngle={-270}
            paddingAngle={2}
            dataKey="value"
            animationDuration={600}
            animationBegin={0}
          >
            <Cell fill={color} stroke="none" />
            <Cell fill="rgba(79, 124, 255, 0.08)" stroke="none" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: size > 140 ? 'var(--font-size-2xl)' : 'var(--font-size-xl)',
          fontWeight: 'var(--font-weight-bold)',
          color,
          lineHeight: 1,
        }}>
          {score}
        </div>
        <div style={{
          fontSize: 'var(--font-size-xs)',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '1px',
        }}>
          Risk Score
        </div>
      </div>
    </div>
  )
}

export default RiskGaugeChart
