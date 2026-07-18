/**
 * VaultWatch Live API Client
 *
 * FIX #6: CSPR.cloud API key removed from client bundle.
 *         All CSPR.cloud calls now go through the FastAPI backend /api/chain
 * FIX #7: No Groq API key in client bundle.
 *         Groq calls go through /api/analyze and /api/rwa
 * FIX #18: Live findings from backend (was hardcoded LIVE_FINDINGS array)
 *          Added missing exports: liveRiskQuery, liveDetectAnomaly, liveAssessRWA,
 *          liveHealth, fetchCSPRPrice, fetchNetworkInfo, getLiveBlockHeight,
 *          CONTRACT_HASHES, LIVE_FINDINGS
 *
 * API base URL: configure via VITE_API_URL env var
 */

// Backend API base URL (never put API keys here)
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── Casper Chain State ─────────────────────────────────────────────────────
// FIX #6: Proxied through backend — CSPR.cloud key stays server-side
export async function fetchChainState() {
  try {
    const resp = await fetch(`${API_BASE}/api/chain`, { timeout: 10000 });
    if (!resp.ok) throw new Error(`Chain API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('Chain state fetch failed, returning cached:', err.message);
    return {
      block_height: null,
      era_id: null,
      timestamp: null,
      network: 'casper-test',
      source: 'cached (offline)',
    };
  }
}

// ─── CSPR Market Price ──────────────────────────────────────────────────────
export async function fetchMarketState() {
  try {
    const resp = await fetch(`${API_BASE}/api/market`);
    if (!resp.ok) throw new Error(`Market API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    // Fallback: fetch directly from CoinGecko (no API key needed for basic price)
    try {
      const cg = await fetch(
        'https://api.coingecko.com/api/v3/simple/price?ids=casper-network&vs_currencies=usd&include_24hr_change=true&include_market_cap=true'
      );
      const data = await cg.json();
      const cspr = data['casper-network'] || {};
      return {
        cspr_price_usd: cspr.usd,
        price_change_24h: cspr.usd_24h_change,
        market_cap_usd: cspr.usd_market_cap,
        timestamp: Date.now() / 1000,
        source: 'CoinGecko (direct)',
      };
    } catch (fallbackErr) {
      return { cspr_price_usd: null, error: err.message };
    }
  }
}

// ─── VaultWatch Findings ────────────────────────────────────────────────────
// FIX #18: Live findings from backend (was hardcoded LIVE_FINDINGS array)
export async function fetchFindings(severity = null, limit = 20) {
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    if (severity) params.append('severity', severity);
    const resp = await fetch(`${API_BASE}/api/findings?${params}`);
    if (!resp.ok) throw new Error(`Findings API returned ${resp.status}`);
    const data = await resp.json();
    return data.findings || [];
  } catch (err) {
    console.warn('Findings fetch failed:', err.message);
    return [];
  }
}

// LIVE_FINDINGS: Fetched from backend, with fallback to empty array.
// Exported so App.jsx ticker can use it. Populated on first fetch.
export let LIVE_FINDINGS = [];

export async function refreshLiveFindings(severity = null, limit = 20) {
  const findings = await fetchFindings(severity, limit);
  LIVE_FINDINGS = findings;
  return findings;
}

// ─── Risk Analysis (via FastAPI backend) ────────────────────────────────────
// FIX #18: liveRiskQuery — was missing; calls backend /api/analyze
export async function liveRiskQuery({ query, protocol }) {
  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, protocol, event_type: 'risk_query' }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Analysis API returned ${resp.status}`);
    }
    return await resp.json();
  } catch (err) {
    console.error('Risk query failed:', err.message);
    return {
      result: {
        summary: `Risk analysis unavailable: ${err.message}`,
        risk_factors: [],
        confidence: 0,
        groq_model: 'offline',
      },
    };
  }
}

// ─── Anomaly Detection (via FastAPI backend) ───────────────────────────────
// FIX #18: liveDetectAnomaly — was missing; calls backend /api/analyze
export async function liveDetectAnomaly(metrics) {
  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address: metrics.address || 'unknown',
        amount_cspr: parseFloat(metrics.tvl) || 0,
        event_type: 'anomaly_detection',
        metrics,
      }),
    });
    if (!resp.ok) throw new Error(`Anomaly API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.error('Anomaly detection failed:', err.message);
    return {
      risk_score: 0,
      anomalies: [],
      recommendation: 'Backend unavailable — cannot assess anomaly risk.',
      agent: 'AnomalyAgent (offline)',
      confidence: 0,
    };
  }
}

// ─── RWA Assessment (via FastAPI backend) ──────────────────────────────────
// FIX #18: liveAssessRWA — was missing; calls backend /api/rwa
export async function liveAssessRWA(asset) {
  try {
    const assetType = asset.asset_type || 'stablecoin';
    const resp = await fetch(`${API_BASE}/api/rwa?asset_type=${encodeURIComponent(assetType)}`);
    if (!resp.ok) throw new Error(`RWA API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.error('RWA assessment failed:', err.message);
    return {
      assessment: {
        verdict: 'REVIEW',
        risk_score: 50,
        notes: `RWA assessment unavailable: ${err.message}`,
        groq_model: 'offline',
      },
    };
  }
}

// ─── Health Check ───────────────────────────────────────────────────────────
// FIX #18: liveHealth — was missing; calls backend /health
export async function liveHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`);
    if (!resp.ok) return { status: 'error', groq_connected: false, code: resp.status };
    const data = await resp.json();
    return {
      status: data.status || 'ok',
      groq_connected: data.groq_connected ?? false,
      version: data.version,
      agents: data.agents,
      contracts: data.contracts,
    };
  } catch (err) {
    return { status: 'offline', groq_connected: false, error: err.message };
  }
}

// ─── CSPR Price (CoinGecko direct, no key needed) ──────────────────────────
// FIX #18: fetchCSPRPrice — was missing; returns formatted price data
export async function fetchCSPRPrice() {
  try {
    const cg = await fetch(
      'https://api.coingecko.com/api/v3/simple/price?ids=casper-network&vs_currencies=usd&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true'
    );
    if (!cg.ok) throw new Error(`CoinGecko returned ${cg.status}`);
    const data = await cg.json();
    const cspr = data['casper-network'] || {};
    return {
      usd: cspr.usd,
      change_24h: cspr.usd_24h_change,
      market_cap: cspr.usd_market_cap,
      vol_24h: cspr.usd_24h_vol,
      source: 'CoinGecko',
    };
  } catch (err) {
    console.warn('CSPR price fetch failed:', err.message);
    return null;
  }
}

// ─── Network Info (via FastAPI backend) ─────────────────────────────────────
// FIX #18: fetchNetworkInfo — was missing; calls backend /api/chain
export async function fetchNetworkInfo() {
  try {
    const resp = await fetch(`${API_BASE}/api/chain`);
    if (!resp.ok) throw new Error(`Chain API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('Network info fetch failed:', err.message);
    return null;
  }
}

// ─── Live Block Height (local estimate + backend sync) ─────────────────────
// FIX #18: getLiveBlockHeight — was missing; estimates block height
let _blockHeight = 2847391;
let _lastBlockTime = Date.now();

export function getLiveBlockHeight() {
  const elapsed = (Date.now() - _lastBlockTime) / 1000;
  _blockHeight += Math.floor(elapsed / 30); // ~1 block per 30s on Casper
  _lastBlockTime = Date.now();
  return _blockHeight;
}

export function updateBlockHeight(height) {
  if (height && height > _blockHeight) {
    _blockHeight = height;
    _lastBlockTime = Date.now();
  }
}

// ─── Risk Analysis (kept for backward compat) ──────────────────────────────
export async function analyzeAddress(address, amountCspr = 0, eventType = 'token_transfer', apiKey = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (apiKey) headers['X-API-Key'] = apiKey;

  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        address,
        amount_cspr: amountCspr,
        event_type: eventType,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Analysis API returned ${resp.status}`);
    }
    return await resp.json();
  } catch (err) {
    console.error('Risk analysis failed:', err.message);
    throw err;
  }
}

// ─── RWA Risk (kept for backward compat) ───────────────────────────────────
export async function fetchRwaRisk(assetType = 'stablecoin') {
  try {
    const resp = await fetch(`${API_BASE}/api/rwa?asset_type=${encodeURIComponent(assetType)}`);
    if (!resp.ok) throw new Error(`RWA API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('RWA risk fetch failed:', err.message);
    return { error: err.message, asset_type: assetType };
  }
}

// ─── Current Policy ─────────────────────────────────────────────────────────
export async function fetchCurrentPolicy() {
  try {
    const resp = await fetch(`${API_BASE}/api/policy`);
    if (!resp.ok) throw new Error(`Policy API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    return { error: err.message, version: 1, source: 'default' };
  }
}

// ─── x402 Intel Query ───────────────────────────────────────────────────────
export async function fetchIntelWithX402(severity = null, limit = 10, paymentHeader = null) {
  const headers = {};
  if (paymentHeader) headers['X-Payment'] = paymentHeader;

  const params = new URLSearchParams({ limit: String(limit) });
  if (severity) params.append('severity', severity);

  const resp = await fetch(`${API_BASE}/api/intel?${params}`, { headers });

  if (resp.status === 402) {
    const x402Data = await resp.json();
    return { status: 402, x402Required: true, paymentParams: x402Data };
  }

  if (!resp.ok) throw new Error(`Intel API returned ${resp.status}`);
  return { status: 200, data: await resp.json() };
}

// ─── Health Check (kept for backward compat) ──────────────────────────────
export async function checkApiHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`);
    if (!resp.ok) return { status: 'error', code: resp.status };
    return await resp.json();
  } catch (err) {
    return { status: 'offline', error: err.message };
  }
}

// ─── Spans (via FastAPI backend) ───────────────────────────────────────────
// FIX #18: fetchSpans — calls backend /api/spans
export async function fetchSpans() {
  try {
    const resp = await fetch(`${API_BASE}/api/spans`);
    if (!resp.ok) throw new Error(`Spans API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('Spans fetch failed:', err.message);
    return { spans: [] };
  }
}

// ─── Audit Log (via FastAPI backend) ───────────────────────────────────────
// FIX #18: fetchAuditLog — calls backend /api/audit
export async function fetchAuditLog() {
  try {
    const resp = await fetch(`${API_BASE}/api/audit`);
    if (!resp.ok) throw new Error(`Audit API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('Audit log fetch failed:', err.message);
    return { entries: [], total: 0 };
  }
}

// ─── Write Audit (via FastAPI backend) ──────────────────────────────────────
// FIX #18: writeAuditEntry — calls backend /api/audit with POST
export async function writeAuditEntry({ action, actor, details }) {
  try {
    const resp = await fetch(`${API_BASE}/api/audit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, actor, details }),
    });
    if (!resp.ok) throw new Error(`Audit write API returned ${resp.status}`);
    return await resp.json();
  } catch (err) {
    console.warn('Audit write failed:', err.message);
    return { success: false, error: err.message };
  }
}

// ─── Contract Explorer Links & Hashes ──────────────────────────────────────
export const CONTRACT_EXPLORER_LINKS = {
  AuditTrail: 'https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6336a7',
  SentinelRegistry: 'https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c',
  RiskOracle: 'https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d',
  SentinelCredit: 'https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71',
  AgentBehaviorIndex: 'https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0',
  SentinelAlertLog: 'https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925',
  RiskPolicyManager: 'https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e',
  SubscriberVault: 'https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d',
};

// FIX #18: CONTRACT_HASHES — real deploy hashes for all 8 contracts
export const CONTRACT_HASHES = {
  AuditTrail: 'b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6336a7',
  SentinelRegistry: '9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c',
  RiskOracle: 'e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d',
  SentinelCredit: '0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71',
  AgentBehaviorIndex: '05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0',
  SentinelAlertLog: '53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925',
  RiskPolicyManager: '93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e',
  SubscriberVault: '6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d',
};

export const DEPLOYER_ACCOUNT = '0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7';
export const DEPLOYER_EXPLORER = `https://testnet.cspr.live/account/${DEPLOYER_ACCOUNT}`;
