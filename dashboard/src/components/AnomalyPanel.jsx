import { useState } from 'react'

const CARD = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
  padding: 20,
  marginBottom: 16,
}

const INPUT = {
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--text)',
  padding: '9px 12px',
  fontSize: 13,
  outline: 'none',
  width: '100%',
}

const DEFAULT_METRICS = {
  protocol: 'CasperSwap',
  tvl: 12000000,
  volume_24h: 2400000,
  price_change_1h: -2.5,
  num_transactions: 340,
  liquidity_ratio: 0.65,
}

export default function AnomalyPanel({ apiFetch }) {
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
      const data = await apiFetch('/anomaly/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...metrics,
          tvl: parseFloat(metrics.tvl),
          volume_24h: parseFloat(metrics.volume_24h),
          price_change_1h: parseFloat(metrics.price_change_1h),
          num_transactions: parseInt(metrics.num_transactions),
          liquidity_ratio: parseFloat(metrics.liquidity_ratio),
        }),
      })
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const riskScore = result?.risk_score ?? 0
  const riskColor = riskScore >= 70 ? 'var(--danger)' : riskScore >= 40 ? 'var(--warning)' : 'var(--success)'

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Anomaly Detection</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        Enter protocol metrics — AnomalyAgent (llama-3.3-70b-versatile) classifies risk with self-correction loop.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Protocol Metrics</h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {[
              { key: 'protocol', label: 'Protocol Name', type: 'text' },
              { key: 'tvl', label: 'TVL (USD)', type: 'number' },
              { key: 'volume_24h', label: '24h Volume (USD)', type: 'number' },
              { key: 'price_change_1h', label: 'Price Change 1h (%)', type: 'number' },
              { key: 'num_transactions', label: 'Transactions (24h)', type: 'number' },
              { key: 'liquidity_ratio', label: 'Liquidity Ratio (0–1)', type: 'number' },
            ].map(field => (
              <div key={field.key}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  {field.label}
                </label>
                <input
                  type={field.type}
                  value={metrics[field.key]}
                  onChange={e => update(field.key, e.target.value)}
                  style={INPUT}
                  step={field.type === 'number' ? 'any' : undefined}
                />
              </div>
            ))}
          </div>
          <button
            onClick={handleDetect}
            disabled={loading}
            style={{
              marginTop: 14,
              width: '100%',
              background: 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '11px 0',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 600,
              opacity: loading ? 0.5 : 1,
            }}
          >
            {loading ? 'Detecting...' : 'Detect Anomalies'}
          </button>
          {error && <p style={{ color: 'var(--danger)', marginTop: 8, fontSize: 13 }}>Error: {error}</p>}
        </div>

        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Risk Score</h2>
          {result ? (
            <>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 52, fontWeight: 800, color: riskColor }}>{riskScore.toFixed(0)}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>out of 100</div>
                {result.confidence !== undefined && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                    Confidence: {(result.confidence * 100).toFixed(0)}%
                  </div>
                )}
              </div>

              {result.anomalies && result.anomalies.length > 0 ? (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Detected Anomalies:</div>
                  {result.anomalies.map((a, i) => (
                    <span key={i} style={{
                      display: 'inline-block', background: '#3a1a1a', color: 'var(--danger)',
                      borderRadius: 4, padding: '3px 8px', fontSize: 12, margin: '0 4px 4px 0',
                    }}>
                      {a}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--success)', fontSize: 13, marginBottom: 12 }}>✓ No anomalies detected</p>
              )}

              {result.recommendation && (
                <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: 12, fontSize: 13 }}>
                  <strong style={{ color: 'var(--text-muted)', fontSize: 11 }}>RECOMMENDATION</strong>
                  <p style={{ marginTop: 4 }}>{result.recommendation}</p>
                </div>
              )}
              {result.agent && (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                  Classified by: {result.agent}
                </div>
              )}
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 13 }}>
              Enter metrics and click detect to see results
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
