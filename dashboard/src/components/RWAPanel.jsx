import { useState } from 'react'
import { CONTRACT_HASHES } from '../liveApi.js'
import { GlassCard } from '../ui/GlassCard.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { SkeletonCard, SkeletonLine } from '../ui/Skeleton.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { Badge, SourceBadge } from '../ui/Badge.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { AnimatedCounter } from '../ui/AnimatedCounter.jsx'

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

const VERDICT_GLOW = {
  APPROVED: 'success',
  REJECTED: 'danger',
  REVIEW:   'warning',
}

const VERDICT_ICON = {
  APPROVED: '✓',
  REJECTED: '✗',
  REVIEW:   '⚠',
}

const VERDICT_VARIANT = {
  APPROVED: 'success',
  REJECTED: 'danger',
  REVIEW:   'warning',
}

export default function RWAPanel({ api, addToast }) {
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
      addToast({ type: 'success', message: `RWA assessment complete: verdict ${data.assessment?.verdict || 'pending'}` })
    } catch (e) {
      setError(e.message)
      addToast({ type: 'error', message: `RWA assessment failed: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  const verdict = result?.verdict

  return (
    <div>
      <PageHeader
        icon="📊"
        badge="RWA"
        title="RWA Assessment"
        subtitle="RWAAgent (Groq Compound · compound-beta) with live web intelligence · on-chain verdict via AuditTrail + RiskOracle on Casper."
      />

      {/* Quick presets */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>Quick load:</span>
        {PRESET_ASSETS.map(p => (
          <GradientBtn
            key={p.label}
            variant="ghost"
            size="sm"
            onClick={() => loadPreset(p)}
          >
            {p.label}
          </GradientBtn>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
        {/* Input */}
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
            Asset Details
          </h2>
          <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
            <Input
              label="Asset ID"
              value={asset.asset_id}
              onChange={e => update('asset_id', e.target.value)}
            />
            <Input
              label="Asset Type"
              type="select"
              value={asset.asset_type}
              onChange={e => update('asset_type', e.target.value)}
            >
              <option value="treasury_bill">Treasury Bill</option>
              <option value="treasury_bond">Treasury Bond</option>
              <option value="corporate_bond">Corporate Bond</option>
              <option value="real_estate">Real Estate</option>
              <option value="commodity">Commodity</option>
              <option value="equity">Equity</option>
              <option value="loan">Loan</option>
            </Input>
            <Input
              label="Issuer"
              value={asset.issuer}
              onChange={e => update('issuer', e.target.value)}
            />
            <Input
              label="Collateral Ratio"
              type="number"
              step="0.01"
              value={asset.collateral_ratio}
              onChange={e => update('collateral_ratio', e.target.value)}
            />
            <Input
              label="Maturity (days)"
              type="number"
              value={asset.maturity_days}
              onChange={e => update('maturity_days', e.target.value)}
            />
            <Input
              label="Credit Rating"
              value={asset.credit_rating}
              onChange={e => update('credit_rating', e.target.value)}
              placeholder="AAA / AA / A / BBB / BB / B"
            />
          </div>
          <GradientBtn
            onClick={handleAssess}
            disabled={loading}
            loading={loading}
            style={{ marginTop: 'var(--space-md)', width: '100%' }}
          >
            {loading ? 'Assessing via Groq Compound...' : 'Assess Asset via Groq Compound'}
          </GradientBtn>
          {error && (
            <GlassCard glow="danger" style={{ marginTop: 'var(--space-sm)', padding: 'var(--space-sm)' }}>
              <span style={{ color: 'var(--danger)', fontSize: 'var(--font-size-sm)' }}>⚠ {error}</span>
            </GlassCard>
          )}
        </GlassCard>

        {/* Result */}
        <GlassCard>
          <h2 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', marginBottom: 'var(--space-md)' }}>
            Assessment Verdict
          </h2>
          {loading && !result ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', paddingTop: 20 }}>
              <SkeletonLine width="100%" height={80} />
              <SkeletonLine width="60%" height={20} />
              <SkeletonLine width="80%" height={40} />
            </div>
          ) : result ? (
            <>
              {/* Verdict card with dramatic gradient glow */}
              <GlassCard glow={VERDICT_GLOW[verdict]} style={{
                textAlign: 'center',
                marginBottom: 'var(--space-md)',
                padding: 'var(--space-lg)',
                background: verdict === 'APPROVED' ? 'rgba(34, 197, 94, 0.06)'
                  : verdict === 'REJECTED' ? 'rgba(239, 68, 68, 0.06)'
                  : 'rgba(245, 158, 11, 0.06)',
              }}>
                <div style={{ fontSize: 40, fontWeight: 'var(--font-weight-bold)', color: verdict === 'APPROVED' ? 'var(--success)' : verdict === 'REJECTED' ? 'var(--danger)' : 'var(--warning)' }}>
                  {VERDICT_ICON[verdict]} {verdict}
                </div>
                {result.risk_score !== undefined && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)', marginTop: 4 }}>
                    Risk Score: <strong style={{ color: verdict === 'APPROVED' ? 'var(--success)' : verdict === 'REJECTED' ? 'var(--danger)' : 'var(--warning)' }}>
                      <AnimatedCounter value={result.risk_score} formatter={v => Math.round(v)} />
                    </strong>/100
                  </div>
                )}
                {result._source && <div style={{ marginTop: 8 }}><SourceBadge source={result._source} /></div>}
              </GlassCard>

              {result.notes && (
                <GlassCard style={{ padding: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>AI Assessment</div>
                  <div style={{ fontSize: 'var(--font-size-sm)', lineHeight: 1.6 }}>{result.notes}</div>
                </GlassCard>
              )}

              {result.collateral_assessment && (
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 4 }}>
                  <strong>Collateral:</strong> {result.collateral_assessment}
                </div>
              )}

              {result.regulatory_status && (
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 8 }}>
                  <strong>Regulatory:</strong> {result.regulatory_status}
                </div>
              )}

              {result.risk_factors && result.risk_factors.length > 0 && (
                <div style={{ marginBottom: 'var(--space-md)' }}>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Risk Factors</div>
                  {result.risk_factors.map((f, i) => (
                    <Badge key={i} variant="warning" size="sm" style={{ marginBottom: 4, display: 'inline-flex' }}>▸ {f}</Badge>
                  ))}
                </div>
              )}

              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 3 }}>
                {result.groq_model && <span>Model: {result.groq_model}</span>}
                <span>
                  Written to:{' '}
                  <a href={`https://testnet.cspr.live/deploy/${CONTRACT_HASHES.RiskPolicyManager}`}
                    target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)', fontFamily: 'var(--font)' }}>
                    RiskOracle deploy ↗
                  </a>
                </span>
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 40, fontSize: 'var(--font-size-sm)' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>🏦</div>
              Fill asset details and click assess<br />
              <span style={{ fontSize: 'var(--font-size-xs)' }}>Groq Compound · compound-beta · live web intelligence</span>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
