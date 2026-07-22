/**
 * RWAAssetsPanel — Enhanced RWA assessment + hybrid feed data
 * (bonds, commodities, real estate, credit, tokenized) with provenance badges.
 */
import { useState, useEffect } from 'react'
import { GlassCard } from '../ui/GlassCard.jsx'
import { PageHeader } from '../ui/PageHeader.jsx'
import { StatCard } from '../ui/StatCard.jsx'
import { Badge, SeverityBadge, SourceBadge } from '../ui/Badge.jsx'
import { GradientBtn } from '../ui/GradientBtn.jsx'
import { Input } from '../ui/Input.jsx'
import { SkeletonBlock } from '../ui/Skeleton.jsx'

const RWA_ASSET_TYPES = ['bonds', 'commodities', 'real_estate', 'credit', 'tokenized_assets']
const RWA_TYPE_ICONS = { bonds: '🏦', commodities: '🥇', real_estate: '🏠', credit: '💳', tokenized_assets: '🔗' }
const RWA_TYPE_COLORS = {
  bonds: 'var(--accent)',
  commodities: 'var(--warning)',
  real_estate: 'var(--accent2)',
  credit: 'var(--danger)',
  tokenized_assets: 'var(--success)',
}

const DEFAULT_ASSET = {
  asset_id: 'asset-001',
  asset_type: 'bonds',
  collateral_ratio: 1.15,
  valuation_usd: 100000,
}

export function RWAAssetsPanel({ api, addToast }) {
  const [feed, setFeed] = useState(null)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState(null)
  const [assessAsset, setAssessAsset] = useState(DEFAULT_ASSET)
  const [assessmentResult, setAssessmentResult] = useState(null)
  const [assessLoading, setAssessLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('feed')

  useEffect(() => {
    loadFeed()
    const interval = setInterval(loadFeed, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadFeed = async () => {
    try {
      const data = await api.getRWAFeed()
      if (data) {
        setFeed(data)
        setSource(data._source || 'fallback')
      }
    } catch (e) {
      // Keep stale data
    } finally {
      setLoading(false)
    }
  }

  const handleAssessRWA = async () => {
    setAssessLoading(true)
    setAssessmentResult(null)
    try {
      const result = await api.assessRWA(assessAsset)
      setAssessmentResult(result)
      addToast({ type: result.assessment?.verdict === 'REJECTED' ? 'error' : 'success', message: `RWA Assessment: ${result.assessment?.verdict}` })
    } catch (e) {
      addToast({ type: 'error', message: `RWA assessment failed: ${e.message}` })
    } finally {
      setAssessLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-lg)' }}>
        <SkeletonBlock height={40} style={{ marginBottom: 'var(--space-lg)' }} />
        <SkeletonBlock height={300} />
      </div>
    )
  }

  const categories = feed?.categories || {}
  const realDataSources = feed?.real_data_sources || {}
  const attestation = feed?.attestation_proof || {}

  return (
    <div className="fade-in" style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="RWA Assets"
        subtitle="Real-World Asset assessment & hybrid data feed"
        icon="📊"
        source={source}
        actions={
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <GradientBtn variant={activeTab === 'feed' ? 'primary' : 'ghost'} size="sm" onClick={() => setActiveTab('feed')}>
              Data Feed
            </GradientBtn>
            <GradientBtn variant={activeTab === 'assess' ? 'primary' : 'ghost'} size="sm" onClick={() => setActiveTab('assess')}>
              Assess RWA
            </GradientBtn>
          </div>
        }
      />

      {/* Stats row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: 'var(--space-md)',
        marginBottom: 'var(--space-lg)',
      }}>
        <StatCard label="Asset Categories" value={Object.keys(categories).length} icon="📁" color="var(--accent2)" />
        <StatCard label="Feed Version" value={feed?.feed_version || '—'} icon="📋" color="var(--text-muted)" animated={false} />
        <StatCard label="Live Sources" value={Object.values(realDataSources).filter(Boolean).length} icon="⚡" color="var(--success)" />
        <StatCard label="Attestation" value={attestation.schema_id ? 'Verified' : 'None'} icon="✓" color={attestation.schema_id ? 'var(--success)' : 'var(--text-muted)'} animated={false} />
      </div>

      {activeTab === 'feed' ? (
        /* Feed view — categories */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {RWA_ASSET_TYPES.map(typeKey => {
            const cat = categories[typeKey]
            if (!cat) return null
            const icon = RWA_TYPE_ICONS[typeKey]
            const color = RWA_TYPE_COLORS[typeKey]
            const dataSource = cat.data_source || 'unknown'

            return (
              <GlassCard key={typeKey} hover={false} style={{ padding: 'var(--space-lg)' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 'var(--space-md)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                    <span style={{ fontSize: 20 }}>{icon}</span>
                    <span style={{
                      fontSize: 'var(--font-size-lg)',
                      fontWeight: 'var(--font-weight-semibold)',
                      color,
                    }}>
                      {typeKey.replace('_', ' ').replace('tokenized_assets', 'Tokenized Assets')}
                    </span>
                  </div>
                  <SourceBadge source={dataSource} />
                </div>

                {/* Category-specific data */}
                {typeKey === 'bonds' && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Treasury 10Y: <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{cat.treasury_yield_10y?.toFixed(2)}%</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      BAA Spread: <span style={{ color: 'var(--warning)', fontFamily: 'var(--font-mono)' }}>{cat.corporate_spread_baa?.toFixed(2)}%</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Default Prob: <span style={{ color: 'var(--danger)', fontFamily: 'var(--font-mono)' }}>{((cat.default_probability || 0) * 100).toFixed(2)}%</span>
                    </div>
                  </div>
                )}

                {typeKey === 'commodities' && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Gold: <span style={{ color: 'var(--warning)', fontFamily: 'var(--font-mono)' }}>${(cat.gold_price_usd || 0).toFixed(0)}</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Silver: <span style={{ color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>${(cat.silver_price_usd || 0).toFixed(1)}</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Oil: <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>${(cat.oil_price_usd || 0).toFixed(0)}</span>
                    </div>
                  </div>
                )}

                {typeKey === 'real_estate' && (
                  <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>
                    Real estate assets with occupancy and location risk metrics
                  </div>
                )}

                {typeKey === 'credit' && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Avg Rating: <span style={{ color: 'var(--accent)' }}>{cat.average_rating}</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Default Rate: <span style={{ color: 'var(--danger)', fontFamily: 'var(--font-mono)' }}>{((cat.default_rate || 0) * 100).toFixed(2)}%</span>
                    </div>
                  </div>
                )}

                {typeKey === 'tokenized_assets' && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      CSPR: <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>${(cat.cspr_price_usd || 0).toFixed(4)}</span>
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)' }}>
                      Stablecoin Depeg Max: <span style={{ color: 'var(--warning)', fontFamily: 'var(--font-mono)' }}>{(cat.stablecoin_depeg_max || 0).toFixed(4)}</span>
                    </div>
                  </div>
                )}

                {/* Assets list */}
                {cat.assets?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                    {cat.assets.map((asset, i) => (
                      <div key={asset.id || i} className="glass-row-hover" style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-sm)',
                        padding: 'var(--space-sm)',
                        background: 'rgba(14, 18, 30, 0.3)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--font-size-sm)',
                      }}>
                        <span style={{ fontWeight: 'var(--font-weight-semibold)', color: color }}>{asset.name}</span>
                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          ${typeof asset.value_usd === 'number' ? (asset.value_usd / 1_000_000).toFixed(1) + 'M' : typeof asset.price === 'number' ? asset.price.toFixed(2) : '—'}
                        </span>
                        {asset.risk && <Badge size="xs" colorScheme={asset.risk === 'LOW' ? 'success' : asset.risk === 'HIGH' ? 'danger' : 'warning'}>{asset.risk}</Badge>}
                        {asset.credit_rating && <Badge size="xs" colorScheme="info">{asset.credit_rating}</Badge>}
                        {asset.collateral_ratio && (
                          <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}>
                            CR: {asset.collateral_ratio}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>
            )
          })}

          {/* Data sources status */}
          <GlassCard hover={false} style={{ padding: 'var(--space-md)' }}>
            <div style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-semibold)',
              color: 'var(--text-secondary)',
              marginBottom: 'var(--space-sm)',
            }}>
              Live Data Source Status
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xs)' }}>
              {Object.entries(realDataSources).map(([key, active]) => (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 'var(--font-size-xs)' }}>
                  <span style={{ color: active ? 'var(--success)' : 'var(--text-dark)' }}>{active ? '✓' : '✕'}</span>
                  <span style={{ color: active ? 'var(--text-secondary)' : 'var(--text-dark)', fontFamily: 'var(--font-mono)' }}>{key}</span>
                </div>
              ))}
            </div>
            {attestation.feed_hash && (
              <div style={{
                marginTop: 'var(--space-sm)',
                padding: '6px 10px',
                background: 'rgba(0, 212, 255, 0.06)',
                border: '1px solid var(--border2)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                color: 'var(--accent)',
                fontFamily: 'var(--font-mono)',
              }}>
                Attestation: {attestation.feed_hash} — {attestation.schema_id}
              </div>
            )}
          </GlassCard>
        </div>
      ) : (
        /* Assess RWA view */
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 'var(--space-lg)',
        }}>
          <GlassCard hover={false} style={{ padding: 'var(--space-lg)' }}>
            <div style={{
              fontSize: 'var(--font-size-lg)',
              fontWeight: 'var(--font-weight-semibold)',
              color: 'var(--text)',
              marginBottom: 'var(--space-md)',
            }}>
              RWA Assessment Parameters
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <Input label="Asset ID" value={assessAsset.asset_id} onChange={(v) => setAssessAsset(prev => ({ ...prev, asset_id: v }))} icon="📋" clearable mono />
              <Input label="Asset Type" value={assessAsset.asset_type} onChange={(v) => setAssessAsset(prev => ({ ...prev, asset_type: v }))} icon="📊" clearable />
              <Input label="Collateral Ratio" value={String(assessAsset.collateral_ratio)} onChange={(v) => setAssessAsset(prev => ({ ...prev, collateral_ratio: Number(v) || 0 }))} icon="⚖️" mono />
              <Input label="Valuation (USD)" value={String(assessAsset.valuation_usd)} onChange={(v) => setAssessAsset(prev => ({ ...prev, valuation_usd: Number(v) || 0 }))} icon="$" mono />
            </div>
            <GradientBtn
              variant="primary"
              onClick={handleAssessRWA}
              loading={assessLoading}
              fullWidth
              style={{ marginTop: 'var(--space-lg)' }}
              icon="📊"
            >
              Assess RWA Asset
            </GradientBtn>
          </GlassCard>

          {/* Assessment results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            {assessmentResult ? (
              <GlassCard hover={false} glow glowColor={assessmentResult.assessment?.verdict === 'REJECTED' ? 'danger' : assessmentResult.assessment?.verdict === 'APPROVED' ? 'success' : 'violet'} style={{ padding: 'var(--space-lg)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
                  <SeverityBadge severity={
                    assessmentResult.assessment?.verdict === 'REJECTED' ? 'CRITICAL' :
                    assessmentResult.assessment?.verdict === 'REVIEW' ? 'MEDIUM' : 'LOW'
                  } />
                  <Badge size="md" colorScheme={
                    assessmentResult.assessment?.verdict === 'APPROVED' ? 'success' :
                    assessmentResult.assessment?.verdict === 'REJECTED' ? 'danger' : 'warning'
                  }>
                    {assessmentResult.assessment?.verdict}
                  </Badge>
                  <SourceBadge source={assessmentResult._source} />
                </div>

                <div style={{
                  fontSize: 'var(--font-size-2xl)',
                  fontWeight: 'var(--font-weight-bold)',
                  color: assessmentResult.assessment?.risk_score > 70 ? 'var(--danger)' : 'var(--warning)',
                  marginBottom: 'var(--space-sm)',
                }}>
                  Risk Score: {assessmentResult.assessment?.risk_score}/100
                </div>

                <div style={{
                  fontSize: 'var(--font-size-md)',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  marginBottom: 'var(--space-md)',
                }}>
                  {assessmentResult.assessment?.notes}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                  {assessmentResult.assessment?.risk_factors?.map((rf, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: 'var(--font-size-sm)',
                      color: 'var(--text-muted)',
                    }}>
                      <span style={{ color: 'var(--danger)' }}>•</span> {rf}
                    </div>
                  ))}
                </div>

                <div style={{
                  marginTop: 'var(--space-md)',
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  Collateral: {assessmentResult.assessment?.collateral_assessment}
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Regulatory: {assessmentResult.assessment?.regulatory_status}
                </div>
              </GlassCard>
            ) : (
              <GlassCard hover={false} style={{
                padding: 'var(--space-xl)',
                textAlign: 'center',
                color: 'var(--text-muted)',
              }}>
                <div style={{ fontSize: 40, marginBottom: 8 }}>📊</div>
                Configure asset parameters and run assessment
              </GlassCard>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default RWAAssetsPanel
