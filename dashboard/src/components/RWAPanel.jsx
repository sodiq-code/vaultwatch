import { useState, useEffect } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }
const INPUT = { background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }

const DEFAULT_ASSET = {
  asset_id:        'us-tbill-2026-001',
  asset_type:      'treasury_bill',
  issuer:          'US Department of Treasury',
  collateral_ratio: 1.05,
  maturity_days:   91,
  credit_rating:   'AAA',
}

const PRESET_ASSETS = [
  { label: 'US T-Bill', asset_id: 'us-tbill-2026-001', asset_type: 'treasury_bill', issuer: 'US Department of Treasury', collateral_ratio: 1.05, maturity_days: 91, credit_rating: 'AAA' },
  { label: 'Corp Bond (ACME)', asset_id: 'corp-bond-acme-2027', asset_type: 'corporate_bond', issuer: 'ACME Corp', collateral_ratio: 0.92, maturity_days: 365, credit_rating: 'BB' },
  { label: 'Solar Farm TX', asset_id: 'solar-farm-tx-001', asset_type: 'real_estate', issuer: 'Green Energy LLC', collateral_ratio: 1.15, maturity_days: 730, credit_rating: 'A' },
  { label: 'NG T-Bill', asset_id: 'ng-tbill-001', asset_type: 'treasury_bill', issuer: 'Central Bank of Nigeria', collateral_ratio: 1.05, maturity_days: 91, credit_rating: 'B+' },
]

export default function RWAPanel({ api }) {
  const [asset, setAsset] = useState(DEFAULT_ASSET)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const update = (k, v) => setAsset(a => ({ ...a, [k]: v }))

  const loadPreset = (preset) => {
    const { label, ...assetData } = preset
    setAsset(assetData)
    setResult(null)
    setError(null)
  }

  const handleAssess = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.assessRWA({
        ...asset,
        collateral_ratio: parseFloat(asset.collateral_ratio),
        maturity_days:    parseInt(asset.maturity_days),
      })
      setResult(data.assessment)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const verdict = result?.verdict
  const verdictColor = verdict === 'APPROVED' ? '#22c55e' : verdict === 'REJECTED' ? '#ef4444' : '#f59e0b'
  const verdictBg   = verdict === 'APPROVED' ? '#0a2a0a' : verdict === 'REJECTED' ? '#2a0a0a' : '#2a1a00'
  const verdictIcon = verdict === 'APPROVED' ? '✓' : verdict === 'REJECTED' ? '✗' : '⚠'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>RWA Assessment</h1>
        <span style={{
          background: '#0a2a0a', border: '1px solid #22c55e40',
          color: '#22c55e', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4, letterSpacing: 0.5,
        }}>
          ● LIVE GROQ AI
        </span>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        RWAAgent (Groq Compound · compound-beta) with live web intelligence · on-chain verdict via AuditTrail + RiskOracle on Casper.
      </p>

      {/* Quick presets */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', alignSelf: 'center' }}>Quick load:</span>
        {PRESET_ASSETS.map(p => (
          <button key={p.label} onClick={() => loadPreset(p)} style={{
            background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 6, color: 'var(--text)', padding: '5px 12px',
            cursor: 'pointer', fontSize: 12,
          }}>
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Input */}
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Asset Details</h2>
          <div style={{ display: 'grid', gap: 10 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Asset ID</label>
              <input value={asset.asset_id} onChange={e => update('asset_id', e.target.value)} style={INPUT} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Asset Type</label>
              <select value={asset.asset_type} onChange={e => update('asset_type', e.target.value)} style={INPUT}>
                <option value="treasury_bill">Treasury Bill</option>
                <option value="treasury_bond">Treasury Bond</option>
                <option value="corporate_bond">Corporate Bond</option>
                <option value="real_estate">Real Estate</option>
                <option value="commodity">Commodity</option>
                <option value="equity">Equity</option>
                <option value="loan">Loan</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Issuer</label>
              <input value={asset.issuer} onChange={e => update('issuer', e.target.value)} style={INPUT} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Collateral Ratio</label>
              <input type="number" step="0.01" value={asset.collateral_ratio} onChange={e => update('collateral_ratio', e.target.value)} style={INPUT} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Maturity (days)</label>
              <input type="number" value={asset.maturity_days} onChange={e => update('maturity_days', e.target.value)} style={INPUT} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Credit Rating</label>
              <input value={asset.credit_rating} onChange={e => update('credit_rating', e.target.value)} style={INPUT} placeholder="AAA / AA / A / BBB / BB / B" />
            </div>
          </div>
          <button onClick={handleAssess} disabled={loading}
            style={{
              marginTop: 14, width: '100%', background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: 8, padding: '11px 0',
              cursor: 'pointer', fontSize: 14, fontWeight: 600, opacity: loading ? 0.5 : 1,
            }}>
            {loading ? '⟳ Assessing via Groq Compound...' : 'Assess Asset via Groq Compound'}
          </button>
          {error && <p style={{ color: 'var(--danger)', marginTop: 8, fontSize: 13 }}>⚠ {error}</p>}
        </div>

        {/* Result */}
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Assessment Verdict</h2>
          {result ? (
            <>
              <div style={{
                background: verdictBg,
                border: `1px solid ${verdictColor}40`,
                borderRadius: 10, padding: '20px 24px',
                textAlign: 'center', marginBottom: 14,
              }}>
                <div style={{ fontSize: 40, fontWeight: 800, color: verdictColor }}>
                  {verdictIcon} {verdict}
                </div>
                {result.risk_score !== undefined && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
                    Risk Score: <strong style={{ color: verdictColor }}>{result.risk_score}</strong>/100
                  </div>
                )}
              </div>

              {result.notes && (
                <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '12px 14px', fontSize: 13, marginBottom: 12, lineHeight: 1.6 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>AI Assessment</div>
                  {result.notes}
                </div>
              )}

              {result.collateral_assessment && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                  <strong>Collateral:</strong> {result.collateral_assessment}
                </div>
              )}

              {result.regulatory_status && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                  <strong>Regulatory:</strong> {result.regulatory_status}
                </div>
              )}

              {result.risk_factors && result.risk_factors.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Risk Factors</div>
                  {result.risk_factors.map((f, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#f59e0b', marginBottom: 3 }}>▸ {f}</div>
                  ))}
                </div>
              )}

              <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 3 }}>
                {result.groq_model && <span>Model: {result.groq_model}</span>}
                <span>
                  Written to:{' '}
                  <a href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.RiskOracle}`}
                    target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)', fontFamily: 'monospace' }}>
                    RiskOracle contract ↗
                  </a>
                </span>
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 13 }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>🏦</div>
              Fill asset details and click assess<br />
              <span style={{ fontSize: 11 }}>Groq Compound · compound-beta · live web intelligence</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
