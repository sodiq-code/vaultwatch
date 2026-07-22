"""Integration tests — Groq API key server-side proxy (Critical Fix 7).

Verifies that:
  1. `VITE_GROQ_API_KEY` does NOT appear in any file under `dashboard/` (it
     would be shipped to the browser bundle by Vite).
  2. `dashboard/src/liveApi.js` has NO `GROQ_API_KEY`, NO `GROQ_URL`, NO
     `groqCall`, NO `import.meta.env.VITE_GROQ`, NO direct `api.groq.com`
     URL, and NO `Authorization: Bearer` header for Groq.
  3. `dashboard/src/liveApi.js` DOES call `/agent/risk-query`,
     `/agent/anomaly-detect`, `/agent/rwa-assess`, and `/agent/health`.
  4. `api/main.py` exposes all four new `/agent/*` endpoints.
  5. `api/main.py` reads `GROQ_API_KEY` from `os.getenv` (NOT from any
     client-supplied header, query param, or body field).
  6. None of the new `/agent/*` endpoints accept a `groq_api_key` or
     `api_key` parameter from the client.
  7. `.env.example` does NOT contain `VITE_GROQ_API_KEY`.
  8. Functional smoke tests using FastAPI TestClient verify each endpoint
     returns the expected dashboard-shaped response.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DASHBOARD_DIR = ROOT / "dashboard"
LIVEAPI = DASHBOARD_DIR / "src" / "liveApi.js"
API_MAIN = ROOT / "api" / "main.py"
ENV_EXAMPLE = ROOT / ".env.example"


# Source file extensions to scan for VITE_GROQ_API_KEY. Excludes binaries,
# lockfiles, node_modules, dist, etc.
_SCANNABLE_EXTS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".example",
    ".env",
    ".sh",
    ".html",
    ".css",
    ".ini",
    ".cfg",
}

_SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
}


def _walk_dashboard_source_files(root: Path):
    """Yield source files under dashboard/ to scan for VITE_GROQ_API_KEY."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            stem = Path(fname).name
            if ext not in _SCANNABLE_EXTS and not stem.startswith(".env"):
                continue
            if fname in {"package-lock.json", "bun.lockb", "yarn.lock"}:
                continue
            if ext in {".wasm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}:
                continue
            yield Path(dirpath) / fname


# ---------------------------------------------------------------------------
# §1  VITE_GROQ_API_KEY must NOT appear anywhere in dashboard/
# ---------------------------------------------------------------------------


def test_vite_groq_api_key_not_in_dashboard():
    """VITE_GROQ_API_KEY must NOT appear in any file under dashboard/.

    Vite ships any `VITE_*` env var to the browser bundle, so even a stray
    comment referencing it could leak through (or mislead a future dev into
    setting it). The Groq key must live server-side in GROQ_API_KEY only.
    """
    assert DASHBOARD_DIR.exists(), "dashboard/ directory not found"
    matches = []
    for fpath in _walk_dashboard_source_files(DASHBOARD_DIR):
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        if "VITE_GROQ_API_KEY" in text:
            matches.append(str(fpath.relative_to(ROOT)))
    assert not matches, (
        f"VITE_GROQ_API_KEY found in {len(matches)} dashboard file(s): {matches}. "
        f"The Groq key is server-side only (Critical Fix 7) — Vite ships "
        f"VITE_* values to the browser bundle, so any reference to "
        f"VITE_GROQ_API_KEY must be removed. Use the /api/agent/* proxy instead."
    )


# ---------------------------------------------------------------------------
# §2  dashboard/src/liveApi.js — no client-side Groq key, no direct Groq URL
# ---------------------------------------------------------------------------


def test_liveapi_has_no_groq_api_key_constant():
    """liveApi.js must NOT define a GROQ_API_KEY constant (browser-exposed)."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "GROQ_API_KEY" not in text, "dashboard/src/liveApi.js still references GROQ_API_KEY — the Groq key must be server-side only (Critical Fix 7)."


def test_liveapi_has_no_groq_url_constant():
    """liveApi.js must NOT define a GROQ_URL constant."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "GROQ_URL" not in text, "dashboard/src/liveApi.js still defines GROQ_URL — Groq is now called server-side via /api/agent/* (Critical Fix 7)."


def test_liveapi_has_no_groqcall_helper():
    """liveApi.js must NOT have a groqCall helper function."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "groqCall" not in text, (
        "dashboard/src/liveApi.js still has a groqCall() helper — Groq calls are now proxied server-side via /api/agent/* (Critical Fix 7)."
    )


def test_liveapi_has_no_import_meta_vite_groq():
    """liveApi.js must NOT reference import.meta.env.VITE_GROQ*."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "import.meta.env.VITE_GROQ" not in text, (
        "dashboard/src/liveApi.js still reads import.meta.env.VITE_GROQ* — the Groq key is no longer shipped to the browser (Critical Fix 7)."
    )


def test_liveapi_has_no_direct_groq_url():
    """liveApi.js must NOT call api.groq.com directly."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "api.groq.com" not in text, (
        "dashboard/src/liveApi.js still calls api.groq.com directly — all Groq calls must go through /api/agent/* (Critical Fix 7)."
    )


def test_liveapi_has_no_groq_authorization_bearer_header():
    """liveApi.js must NOT send an `Authorization: Bearer` header for Groq."""
    text = LIVEAPI.read_text(encoding="utf-8")
    # The cspr.cloud proxy sends Authorization via the FastAPI proxy, not
    # from the frontend. Look for any literal Bearer-header construction
    # that references Groq.
    assert "Authorization': `Bearer" not in text, (
        "dashboard/src/liveApi.js still constructs an Authorization: Bearer header for Groq — the key is now injected server-side (Critical Fix 7)."
    )
    assert 'Authorization": "Bearer' not in text, (
        "dashboard/src/liveApi.js still constructs an Authorization: Bearer header for Groq — the key is now injected server-side (Critical Fix 7)."
    )


# ---------------------------------------------------------------------------
# §3  dashboard/src/liveApi.js — must call the /agent/* proxy endpoints
# ---------------------------------------------------------------------------


def test_liveapi_calls_agent_risk_query():
    """liveApi.js must POST to /agent/risk-query."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "/agent/risk-query" in text, "dashboard/src/liveApi.js should call /agent/risk-query (Critical Fix 7)."


def test_liveapi_calls_agent_anomaly_detect():
    """liveApi.js must POST to /agent/anomaly-detect."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "/agent/anomaly-detect" in text, "dashboard/src/liveApi.js should call /agent/anomaly-detect (Critical Fix 7)."


def test_liveapi_calls_agent_rwa_assess():
    """liveApi.js must POST to /agent/rwa-assess."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "/agent/rwa-assess" in text, "dashboard/src/liveApi.js should call /agent/rwa-assess (Critical Fix 7)."


def test_liveapi_calls_agent_health():
    """liveApi.js must GET /agent/health."""
    text = LIVEAPI.read_text(encoding="utf-8")
    assert "/agent/health" in text, "dashboard/src/liveApi.js should call /agent/health (Critical Fix 7)."


# ---------------------------------------------------------------------------
# §4  api/main.py — exposes all four /agent/* endpoints
# ---------------------------------------------------------------------------


def test_api_main_has_agent_health_endpoint():
    """api/main.py must define GET /agent/health."""
    text = API_MAIN.read_text(encoding="utf-8")
    assert '@app.get("/agent/health"' in text, "api/main.py missing GET /agent/health endpoint (Critical Fix 7)."


def test_api_main_has_agent_risk_query_endpoint():
    """api/main.py must define POST /agent/risk-query."""
    text = API_MAIN.read_text(encoding="utf-8")
    assert '@app.post("/agent/risk-query"' in text, "api/main.py missing POST /agent/risk-query endpoint (Critical Fix 7)."


def test_api_main_has_agent_anomaly_detect_endpoint():
    """api/main.py must define POST /agent/anomaly-detect."""
    text = API_MAIN.read_text(encoding="utf-8")
    assert '@app.post("/agent/anomaly-detect"' in text, "api/main.py missing POST /agent/anomaly-detect endpoint (Critical Fix 7)."


def test_api_main_has_agent_rwa_assess_endpoint():
    """api/main.py must define POST /agent/rwa-assess."""
    text = API_MAIN.read_text(encoding="utf-8")
    assert '@app.post("/agent/rwa-assess"' in text, "api/main.py missing POST /agent/rwa-assess endpoint (Critical Fix 7)."


# ---------------------------------------------------------------------------
# §5  api/main.py — reads GROQ_API_KEY from os.getenv only
# ---------------------------------------------------------------------------


def test_api_main_reads_groq_key_from_os_getenv():
    """api/main.py must read GROQ_API_KEY from os.getenv — not from a request
    header, query param, or body field."""
    text = API_MAIN.read_text(encoding="utf-8")
    assert 'os.getenv("GROQ_API_KEY"' in text or 'os.getenv("GROQ_API_KEY",' in text, "api/main.py must read GROQ_API_KEY via os.getenv() (Critical Fix 7)."


def test_api_main_does_not_read_groq_key_from_request_headers():
    """The /agent/* endpoints must NOT read the Groq key from a request header."""
    text = API_MAIN.read_text(encoding="utf-8")
    # Extract the /agent/* section so we don't false-flag the x402 routes
    # (which legitimately read PAYMENT-SIGNATURE headers — not the Groq key).
    agent_section = text[text.find("# /agent/*") :]
    # Strip Python comments — we want to detect actual CODE that reads a
    # client-supplied groq_api_key, not comments that mention the field name
    # while explaining the security policy.
    code_lines = []
    for line in agent_section.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Strip inline comments
        if "#" in line:
            line = line.split("#", 1)[0]
        code_lines.append(line)
    code_only = "\n".join(code_lines)
    assert "groq_api_key" not in code_only, "api/main.py /agent/* endpoints must not accept a groq_api_key field from the client (Critical Fix 7)."


# ---------------------------------------------------------------------------
# §6  api/main.py — /agent/* request models must NOT accept groq_api_key
# ---------------------------------------------------------------------------


def test_agent_request_models_have_no_groq_api_key_field():
    """None of the Agent*Request models in api/main.py may accept a
    `groq_api_key` or `api_key` field from the client."""
    text = API_MAIN.read_text(encoding="utf-8")
    # The Agent*Request models are defined in the /agent/* section.
    agent_section = text[text.find("# /agent/*") :]
    # Strip comments — we want to detect actual model-field declarations
    # (`groq_api_key: str`), not comments that mention the field name while
    # explaining the security policy.
    code_lines = []
    for line in agent_section.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        code_lines.append(line)
    code_only = "\n".join(code_lines)
    forbidden_field_decls = [
        "groq_api_key: str",
        "groq_api_key: Optional",
        "api_key: str",
        "api_key: Optional",
        'request.headers.get("groq_api_key"',
        'request.headers.get("api_key"',
        'request.query_params.get("groq_api_key"',
        'request.query_params.get("api_key"',
    ]
    for token in forbidden_field_decls:
        assert token not in code_only, (
            f"api/main.py /agent/* section accepts '{token}' from the client — the Groq key must come from os.getenv only (Critical Fix 7)."
        )


# ---------------------------------------------------------------------------
# §7  .env.example must NOT document VITE_GROQ_API_KEY
# ---------------------------------------------------------------------------


def test_env_example_has_no_vite_groq_api_key():
    """The .env.example must NOT document VITE_GROQ_API_KEY (it would be
    browser-exposed). The Groq key is server-side only via GROQ_API_KEY.

    We check for an assignment (`VITE_GROQ_API_KEY=...`) rather than the
    bare token, so comments explaining WHY VITE_GROQ_API_KEY must not be
    set are still allowed (and encouraged for documentation purposes).
    """
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0]
        if line.startswith("VITE_GROQ_API_KEY") or "VITE_GROQ_API_KEY=" in line:
            raise AssertionError(".env.example assigns VITE_GROQ_API_KEY — the Groq key is server-side only (Critical Fix 7).")


def test_env_example_documents_server_side_groq_key():
    """The .env.example must still document GROQ_API_KEY (server-side)."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    found_assignment = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if line.startswith("GROQ_API_KEY="):
            found_assignment = True
            break
    assert found_assignment, ".env.example must still document the server-side GROQ_API_KEY assignment."


# ---------------------------------------------------------------------------
# §8  Functional smoke tests — /agent/* endpoints return dashboard shapes
# ---------------------------------------------------------------------------


def _import_app():
    """Import the FastAPI app, force re-import if already loaded."""
    import importlib

    if "api.main" in sys.modules:
        importlib.reload(sys.modules["api.main"])
    import api.main as api_mod

    return api_mod


def test_agent_health_returns_dashboard_shape(monkeypatch):
    """/agent/health must return the same shape as liveApi.js:liveHealth()."""
    api_mod = _import_app()
    from fastapi.testclient import TestClient

    # Mock CoinGecko so no real network call is made
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"casper-network": {"usd": 0.0421}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = TestClient(api_mod.app)
        r = client.get("/agent/health")

    assert r.status_code == 200
    body = r.json()
    # Must match liveApi.js:liveHealth() shape exactly
    expected_keys = {
        "status",
        "version",
        "mode",
        "agents",
        "contracts",
        "groq_connected",
        "cspr_price_usd",
        "network",
    }
    assert expected_keys.issubset(body.keys()), f"/agent/health missing keys: {expected_keys - set(body.keys())}"
    assert body["status"] == "ok"
    assert body["version"] == "4.0.0"
    assert body["mode"] == "live"
    assert body["agents"] == 6
    assert body["contracts"] == 8
    assert isinstance(body["groq_connected"], bool)
    assert body["network"] == "casper-test"
    assert body["cspr_price_usd"] == 0.0421


def test_agent_health_groq_connected_reflects_env(monkeypatch):
    """/agent/health groq_connected must be True iff GROQ_API_KEY is set,
    and the key itself must NEVER appear in the response."""
    monkeypatch.setenv("GROQ_API_KEY", "secret-groq-key-do-not-leak-abc")
    api_mod = _import_app()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"casper-network": {"usd": 0.05}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        r = client.get("/agent/health")

    body = r.json()
    assert body["groq_connected"] is True
    # The key itself must NEVER appear in the response
    assert "secret-groq-key-do-not-leak-abc" not in r.text, "/agent/health leaked the Groq API key in the response body"
    assert "secret-groq-key-do-not-leak-abc" not in str(r.headers), "/agent/health leaked the Groq API key in the response headers"


def test_agent_health_groq_connected_false_when_unset(monkeypatch):
    """groq_connected must be False when GROQ_API_KEY is unset."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    api_mod = _import_app()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"casper-network": {"usd": 0.05}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        r = client.get("/agent/health")

    body = r.json()
    assert body["groq_connected"] is False


def test_agent_risk_query_returns_dashboard_shape(monkeypatch):
    """/agent/risk-query must return the {result: {...}} shape that
    liveApi.js:liveRiskQuery() previously built client-side."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-server-side")
    api_mod = _import_app()

    # Mock the IntelAgent + SafetyGuard so no real Groq call is made
    async def _fake_check(query):
        return {"safe": True, "reason": ""}

    async def _fake_analyze(query, protocol=None, extra_context=None):
        return {
            "summary": "CasperSwap has elevated whale concentration risk.",
            "risk_factors": ["whale_concentration", "low_liquidity"],
            "findings_count": 2,
            "confidence": 0.91,
        }

    intel_mock = MagicMock()
    intel_mock.analyze = _fake_analyze
    safety_mock = MagicMock()
    safety_mock.check = _fake_check

    with patch.object(api_mod, "_get_intel", return_value=intel_mock), patch.object(api_mod, "_get_safety", return_value=safety_mock):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        r = client.post(
            "/agent/risk-query",
            json={"query": "Is CasperSwap safe?", "protocol": "CasperSwap"},
        )

    assert r.status_code == 200
    body = r.json()
    # Must match liveApi.js:liveRiskQuery() shape exactly
    assert "result" in body
    result = body["result"]
    expected_keys = {
        "summary",
        "risk_factors",
        "confidence",
        "severity",
        "recommendation",
        "groq_model",
        "on_chain_contract",
        "on_chain_hash",
    }
    assert expected_keys.issubset(result.keys()), f"/agent/risk-query result missing keys: {expected_keys - set(result.keys())}"
    assert "CasperSwap" in result["summary"] or "whale" in result["summary"].lower()
    assert isinstance(result["risk_factors"], list)
    assert isinstance(result["confidence"], float)
    assert result["groq_model"] == "llama-3.3-70b-versatile"
    assert result["on_chain_contract"] == "RiskOracle"
    assert isinstance(result["on_chain_hash"], str) and len(result["on_chain_hash"]) == 64
    # The Groq key must NEVER appear in the response
    assert "test-key-server-side" not in r.text


def test_agent_anomaly_detect_returns_dashboard_shape(monkeypatch):
    """/agent/anomaly-detect must return the shape that liveApi.js:
    liveDetectAnomaly() previously built client-side."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-server-side")
    api_mod = _import_app()

    from agents.anomaly_agent import AnomalyResult

    async def _fake_detect(metrics):
        return AnomalyResult(
            protocol=metrics["protocol"],
            risk_score=87.0,
            anomalies=["whale_dump", "liquidity_crisis"],
            recommendation="Halt withdrawals immediately",
            timestamp=1234567890.0,
            severity="CRITICAL",
            confidence=0.92,
        )

    anomaly_mock = MagicMock()
    anomaly_mock.detect = _fake_detect

    with patch.object(api_mod, "_get_anomaly", return_value=anomaly_mock):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        r = client.post(
            "/agent/anomaly-detect",
            json={
                "protocol": "CasperSwap",
                "tvl": 10_000_000,
                "volume_24h": 5_000_000,
                "price_change_1h": -35.0,
                "num_transactions": 5000,
                "liquidity_ratio": 0.03,
            },
        )

    assert r.status_code == 200
    body = r.json()
    # Must match liveApi.js:liveDetectAnomaly() shape exactly
    expected_keys = {
        "risk_score",
        "anomalies",
        "recommendation",
        "confidence",
        "agent",
        "severity",
        "self_correction_applied",
        "on_chain_contract",
    }
    assert expected_keys.issubset(body.keys()), f"/agent/anomaly-detect missing keys: {expected_keys - set(body.keys())}"
    assert body["risk_score"] == 87.0
    assert "whale_dump" in body["anomalies"]
    assert body["recommendation"] == "Halt withdrawals immediately"
    assert body["confidence"] == 0.92
    assert "AnomalyAgent" in body["agent"]
    assert body["severity"] == "CRITICAL"
    assert isinstance(body["self_correction_applied"], bool)
    assert body["on_chain_contract"] == "SentinelAlertLog"
    # The Groq key must NEVER appear in the response
    assert "test-key-server-side" not in r.text


def test_agent_rwa_assess_returns_dashboard_shape(monkeypatch):
    """/agent/rwa-assess must return the {assessment: {...}} shape that
    liveApi.js:liveAssessRWA() previously built client-side."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-server-side")
    api_mod = _import_app()

    async def _fake_assess(asset_data):
        return {
            "verdict": "APPROVED",
            "risk_score": 12.0,
            "notes": "High-grade sovereign debt — low default risk.",
            "risk_factors": ["interest_rate_risk"],
        }

    rwa_mock = MagicMock()
    rwa_mock.assess = _fake_assess

    with patch.object(api_mod, "_get_rwa", return_value=rwa_mock):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        r = client.post(
            "/agent/rwa-assess",
            json={
                "asset_id": "us-treasury-10y-001",
                "asset_type": "treasury_bond",
                "issuer": "US Government",
                "collateral_ratio": 1.05,
                "maturity_days": 3650,
                "credit_rating": "AAA",
            },
        )

    assert r.status_code == 200
    body = r.json()
    # Must match liveApi.js:liveAssessRWA() shape exactly
    assert "assessment" in body
    assessment = body["assessment"]
    expected_keys = {
        "verdict",
        "risk_score",
        "notes",
        "risk_factors",
        "groq_model",
        "collateral_assessment",
        "regulatory_status",
        "on_chain_contract",
        "on_chain_hash",
    }
    assert expected_keys.issubset(assessment.keys()), f"/agent/rwa-assess assessment missing keys: {expected_keys - set(assessment.keys())}"
    assert assessment["verdict"] == "APPROVED"
    assert assessment["risk_score"] == 12.0
    assert "sovereign" in assessment["notes"].lower()
    assert assessment["groq_model"] == "compound-beta (Groq Compound)"
    assert assessment["on_chain_contract"] == "RiskPolicyManager"
    assert isinstance(assessment["on_chain_hash"], str) and len(assessment["on_chain_hash"]) == 64
    # The Groq key must NEVER appear in the response
    assert "test-key-server-side" not in r.text


def test_agent_endpoints_do_not_accept_groq_api_key_in_body(monkeypatch):
    """Passing `groq_api_key` in the request body must NOT override the
    server-side GROQ_API_KEY (it should be silently ignored or rejected by
    pydantic, depending on model config). Either way, the response must
    not echo it back."""
    monkeypatch.setenv("GROQ_API_KEY", "real-server-key-xyz")
    api_mod = _import_app()

    from agents.anomaly_agent import AnomalyResult

    captured_metrics = {}

    async def _fake_detect(metrics):
        captured_metrics.update(metrics)
        return AnomalyResult(
            protocol=metrics.get("protocol", ""),
            risk_score=10.0,
            anomalies=[],
            recommendation="ok",
            timestamp=0.0,
        )

    anomaly_mock = MagicMock()
    anomaly_mock.detect = _fake_detect

    with patch.object(api_mod, "_get_anomaly", return_value=anomaly_mock):
        from fastapi.testclient import TestClient

        client = TestClient(api_mod.app)
        # Client tries to inject a fake Groq key — must be ignored by pydantic
        # (extra fields are ignored by default in BaseModel).
        r = client.post(
            "/agent/anomaly-detect",
            json={
                "protocol": "TestProto",
                "tvl": 1_000_000,
                "volume_24h": 100_000,
                "price_change_1h": 1.0,
                "num_transactions": 100,
                "liquidity_ratio": 0.5,
                "groq_api_key": "fake-client-key-attacker-controlled",
                "api_key": "another-fake-key",
            },
        )

    # The endpoint must succeed (pydantic ignores extras by default) and
    # MUST NOT use the client-supplied key — the agent only sees the metrics.
    assert r.status_code == 200
    assert "fake-client-key-attacker-controlled" not in r.text, "/agent/anomaly-detect echoed the client-supplied fake key in the response"
    # Verify the agent only saw the legitimate metrics, not the fake key
    assert "groq_api_key" not in captured_metrics
    assert "api_key" not in captured_metrics
