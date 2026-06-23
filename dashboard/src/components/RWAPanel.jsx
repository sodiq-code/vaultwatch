import { useState, useEffect } from 'react'

const CARD = { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }
const INPUT = { background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', padding: '9px 12px', fontSize: 13, outline: 'none', width: '100%' }

const DEFAULT_ASSET = {
  asset_id: 'us-tbill-2026-001',
  asset_type: 'treasury_bill',
  issuer: 'US Department of Treasury',
  collateral_ratio: 1.05,
  maturity_days: 91,
  credit_rating: 'AAA',
}

export default function RWAPanel({ apiFetch }) {
  const [asset, setAsset] = useState(DEFAULT_ASSET)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [assets, setAssets] = useState([])

  const update = (k, v) => setAsset(a => ({ ...a, [k]: v }))

  const handleAssess = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiFetch('/rwa/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...asset,
          collateral_ratio: parseFloat(asset.collateral_ratio),
          maturity_days: parseInt(asset.maturity_days),
        }),
      })
      setResult(data.assessment)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    apiFetch('/rwa/assets').then(d => setAssets(d.assets || [])).catch(() => {})
  }, [apiFetch])

  const verdict = result?.verdict
  const verdictColor = verdict === 'APPROVED' ? 'var(--success)' : verdict === 'REJECTED' ? 'var(--danger)' : 'var(--warning)'

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>RWA Assessment</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
        Evaluate real-world assets for on-chain tokenisation viability on Casper via Groq Compound web intelligence.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Asset Details</h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {[
              { key: 'asset_id', label: 'Asset ID' },
              { key: 'issuer', label: 'Issuer' },
              { key: 'collateral_ratio', label: 'Collateral Ratio' },
              { key: 'maturity_days', label: 'Maturity (days)' },
              { key: 'credit_rating', label: 'Credit Rating' },
            ].map(f => (
              <div key={f.key}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>{f.label}</label>
                <input value={asset[f.key]} onChange={e => update(f.key, e.target.value)} style={INPUT} />
              </div>
            ))}
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Asset Type</label>
              <select value={asset.asset_type} onChange={e => update('asset_type', e.target.value)}
                style={{ ...INPUT }}>
                <option value="treasury_bill">Treasury Bill</option>
                <option value="treasury_bond">Treasury Bond</option>
                <option value="corporate_bond">Corporate Bond</option>
                <option value="real_estate">Real Estate</option>
                <option value="commodity">Commodity</option>
                <option value="equity">Equity</option>
                <option value="loan">Loan</option>
              </select>
            </div>
          </div>
          <button onClick={handleAssess} disabled={loading}
            style={{ marginTop: 14, width: '100%', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 8, padding: '11px 0', cursor: 'pointer', fontSize: 14, fontWeight: 600, opacity: loading ? 0.5 : 1 }}>
            {loading ? 'Assessing via Groq Compound...' : 'Assess Asset'}
          </button>
          {error && <p style={{ color: 'var(--danger)', marginTop: 8, fontSize: 13 }}>Error: {error}</p>}
        </div>

        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Assessment Result</h2>
          {result ? (
            <>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 36, fontWeight: 800, color: verdictColor }}>
                  {verdict === 'APPROVED' ? '✓ APPROVED' : verdict === 'REJECTED' ? '✗ REJECTED' : '⚠ REVIEW'}
                </div>
                {result.risk_score !== undefined && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
                    Risk Score: {result.risk_score}/100
                  </div>
                )}
              </div>
              {result.notes && (
                <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: 12, fontSize: 13 }}>
                  <strong style={{ color: 'var(--text-muted)', fontSize: 11 }}>NOTES</strong>
                  <p style={{ marginTop: 4 }}>{result.notes}</p>
                </div>
              )}
              {result.groq_model && (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                  Powered by: {result.groq_model}
                </div>
              )}
            </>
          ) : (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 13 }}>
              Fill in asset details and click assess to see the verdict.
            </p>
          )}
        </div>
      </div>

      {assets.length > 0 && (
        <div style={CARD}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Previously Assessed Assets ({assets.length})</h2>
          <div style={{ display: 'grid', gap: 8 }}>
            {assets.map((a, i) => (
              <div key={i} style={{ background: 'var(--surface2)', borderRadius: 8, padding: '10px 14px', fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'monospace' }}>{a.asset_id || a.id}</span>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{a.asset_type}</span>
                  {a.verdict && (
                    <span style={{
                      fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                      background: a.verdict === 'APPROVED' ? '#16321a' : '#3a1a1a',
                      color: a.verdict === 'APPROVED' ? 'var(--success)' : 'var(--danger)',
                    }}>{a.verdict}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
