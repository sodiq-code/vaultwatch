import { useState } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'

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

function RiskGauge({ score }) {
  const color = score >= 70 ? 'var(--danger)' : score >= 40 ? 'var(--warning)' : 'var(--success)'
  const label = score >= 70 ? 'HIGH RISK' : score >= 40 ? 'ELEVATED' : 'NORMAL'
  return (
    <div style={{ textAlign: 'center', marginBottom: 16 }}>
      <div style={{ fontSize: 56, fontWeight: 800, color, lineHeight: 1 }}>{Math.round(score)}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>/ 100 risk score</div>
      <div style={{
        display: 'inline-block', marginTop: 8,
        background: color + '22', color, borderRadius: 4,
        padding: '3px 12px', fontSize: 12, fontWeight: 700, letterSpacing: 0.5,
      }}>{label}</div>
      {/* bar */}
      <div style={{ marginTop: 12, height: 6, borderRadius: 3, background: 'var(--surface2)', overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 3,
          width: `${score}%`,
          background: `linear-gradient(90deg, #22c55e, ${color})`,
          transition: 'width 0.6s ease',
        }} />
      </div>
    </div>
  )
}

export default function AnomalyPanel({ api }) {
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
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Anomaly Detection</h1>
        <span style={{
          background: '#0a2a0a', border: '1px solid #22c55e40',
          color: '#22c55e', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4, letterSpacing: 0.5,
        }}>
          ● LIVE GROQ AI
        </span>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        AnomalyAgent (llama-3.3-70b-versatile) with SelfCorrectionAgent loop · findings written to AuditTrail + RiskOracle on Casper.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Input */}
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Protocol Metrics</h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {FIELDS.map(field => (
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
              marginTop: 14, width: '100%',
              background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: 8,
              padding: '11px 0', cursor: 'pointer',
              fontSize: 14, fontWeight: 600,
              opacity: loading ? 0.5 : 1,
            }}
          >
            {loading ? '⟳ Calling AnomalyAgent via Groq...' : 'Detect Anomalies'}
          </button>
          {error && (
            <div style={{ marginTop: 8, color: 'var(--danger)', fontSize: 13 }}>
              ⚠ {error}
            </div>
          )}
        </div>

        {/* Result */}
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>
            AnomalyAgent Result
          </h2>
          {result ? (
            <>
              <RiskGauge score={result.risk_score ?? 0} />

              {result.anomalies && result.anomalies.length > 0 ? (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    Detected Anomalies
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {result.anomalies.map((a, i) => (
                      <span key={i} style={{
                        background: '#3a1a1a', color: 'var(--danger)',
                        borderRadius: 4, padding: '4px 10px', fontSize: 12, fontWeight: 600,
                      }}>
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <p style={{ color: 'var(--success)', fontSize: 13, marginBottom: 12 }}>
                  ✓ No anomalies detected
                </p>
              )}

              {result.recommendation && (
                <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '10px 12px', fontSize: 13, marginBottom: 10 }}>
                  <strong style={{ color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }}>Recommendation</strong>
                  <p style={{ marginTop: 4, lineHeight: 1.5 }}>{result.recommendation}</p>
                </div>
              )}

              {result.self_correction_applied && (
                <div style={{ background: '#0a1a2a', borderRadius: 6, padding: '6px 10px', fontSize: 11, color: '#3b82f6', marginBottom: 8 }}>
                  ⟳ SelfCorrectionAgent applied — confidence re-evaluated
                </div>
              )}

              <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {result.confidence !== undefined && (
                  <span>Confidence: <strong style={{ color: 'var(--text)' }}>{(result.confidence * 100).toFixed(0)}%</strong></span>
                )}
                {result.agent && <span>Agent: {result.agent}</span>}
                {result.on_chain_contract && (
                  <span>
                    On-chain:{' '}
                    <a
                      href={`https://testnet.cspr.live/contract-package/${CONTRACT_HASHES.AuditTrail}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ color: 'var(--accent)', fontFamily: 'monospace' }}
                    >
                      AuditTrail contract ↗
                    </a>
                  </span>
                )}
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 13 }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>⚠</div>
              Enter protocol metrics and click detect<br />
              <span style={{ fontSize: 11 }}>Real Groq AI · llama-3.3-70b-versatile</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
