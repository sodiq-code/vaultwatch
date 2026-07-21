"""Integration tests — FastAPI API-key auth + per-IP rate limiting.

Verifies the two security middlewares in api/security.py:
  • AuthMiddleware: X-API-Key header check, env-gated, public-path exemption.
  • RateLimitMiddleware: per-IP sliding window, env-gated, 429 + Retry-After.

Both middlewares read config at request time, so monkeypatch.setenv works
without re-importing the app. The rate-limit store is reset between tests via
reset_rate_limiter() for isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(monkeypatch):
    """TestClient with auth + rate limiting disabled (clean baseline)."""
    monkeypatch.delenv("VAULTWATCH_API_KEY", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    from api.security import reset_rate_limiter

    reset_rate_limiter()
    import api.main as api_mod
    from fastapi.testclient import TestClient

    with TestClient(api_mod.app) as c:
        yield c
    reset_rate_limiter()


# ===========================================================================
# AuthMiddleware — X-API-Key header
# ===========================================================================


def test_auth_disabled_by_default_allows_access(client):
    """No VAULTWATCH_API_KEY set → auth disabled → endpoint accessible."""
    r = client.get("/risk/findings")
    assert r.status_code == 200, r.text


def test_auth_enabled_missing_key_returns_401(client, monkeypatch):
    """VAULTWATCH_API_KEY set + no X-API-Key header → 401."""
    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")
    r = client.get("/risk/findings")
    assert r.status_code == 401
    assert "Missing" in r.json()["detail"] or "API key" in r.json()["detail"]
    assert r.headers.get("WWW-Authenticate") == "X-API-Key"


def test_auth_enabled_wrong_key_returns_401(client, monkeypatch):
    """VAULTWATCH_API_KEY set + wrong X-API-Key → 401."""
    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")
    r = client.get("/risk/findings", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid API key"


def test_auth_enabled_correct_key_returns_200(client, monkeypatch):
    """VAULTWATCH_API_KEY set + matching X-API-Key → 200."""
    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")
    r = client.get("/risk/findings", headers={"X-API-Key": "secret-key-123"})
    assert r.status_code == 200, r.text


def test_auth_public_path_exempt(client, monkeypatch):
    """/health is exempt from auth even when VAULTWATCH_API_KEY is set."""
    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_does_not_leak_key_in_response(client, monkeypatch):
    """The configured API key never appears in any response body or header."""
    monkeypatch.setenv("VAULTWATCH_API_KEY", "super-secret-do-not-leak")
    # Wrong key
    r = client.get("/risk/findings", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert "super-secret-do-not-leak" not in r.text
    assert "super-secret-do-not-leak" not in str(r.headers)
    # Missing key
    r2 = client.get("/risk/findings")
    assert r2.status_code == 401
    assert "super-secret-do-not-leak" not in r2.text


def test_auth_uses_constant_time_comparison(client, monkeypatch):
    """AuthMiddleware must use ``hmac.compare_digest`` for the key check, NOT
    Python's ``!=`` operator.

    A non-constant-time ``!=`` short-circuits on the first mismatched byte,
    leaking a timing oracle that lets an attacker recover the API key
    byte-by-byte. This test patches ``hmac.compare_digest`` and asserts it is
    actually called on the auth path — guarding against a regression that
    reintroduces the early-exit ``!=`` short-circuit.
    """
    import api.security as security_mod
    from unittest.mock import patch

    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")

    # Wrong key — must still go through compare_digest (and reject).
    with patch.object(security_mod, "hmac") as fake_hmac:
        # Make compare_digest behave like the real one (constant-time equal check).
        import hmac as real_hmac

        fake_hmac.compare_digest.side_effect = lambda a, b: real_hmac.compare_digest(a, b)
        r = client.get("/risk/findings", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid API key"
    # The middleware MUST have delegated to hmac.compare_digest — not used
    # a bare ``!=`` short-circuit. This is the regression guard.
    assert fake_hmac.compare_digest.called, (
        "AuthMiddleware did not call hmac.compare_digest — a non-constant-time "
        "``!=`` short-circuit may have been reintroduced, leaking a timing oracle."
    )

    # Correct key — must also go through compare_digest (and accept).
    with patch.object(security_mod, "hmac") as fake_hmac:
        import hmac as real_hmac

        fake_hmac.compare_digest.side_effect = lambda a, b: real_hmac.compare_digest(a, b)
        r2 = client.get("/risk/findings", headers={"X-API-Key": "secret-key-123"})
    assert r2.status_code == 200
    assert fake_hmac.compare_digest.called


# ===========================================================================
# RateLimitMiddleware — per-IP sliding window
# ===========================================================================


def test_rate_limit_disabled_by_default(client):
    """No RATE_LIMIT_PER_MINUTE set → disabled → many requests succeed."""
    for _ in range(20):
        r = client.get("/risk/findings")
        assert r.status_code == 200, r.text


def test_rate_limit_enabled_returns_429_after_limit(client, monkeypatch):
    """RATE_LIMIT_PER_MINUTE=2 → 3rd request within window is 429."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    r1 = client.get("/risk/findings")
    r2 = client.get("/risk/findings")
    r3 = client.get("/risk/findings")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    body = r3.json()
    assert body["detail"] == "Rate limit exceeded"
    assert body["limit"] == 2
    assert "Retry-After" in r3.headers
    assert int(r3.headers["Retry-After"]) >= 1
    assert r3.headers["X-RateLimit-Limit"] == "2"
    assert r3.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_success_responses_include_headers(client, monkeypatch):
    """Successful responses carry X-RateLimit-Limit + X-RateLimit-Remaining."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10")
    r = client.get("/risk/findings")
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "10"
    assert int(r.headers["X-RateLimit-Remaining"]) >= 0


def test_rate_limit_public_path_exempt(client, monkeypatch):
    """/health is exempt from rate limiting — unlimited requests succeed."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    for _ in range(10):
        r = client.get("/health")
        assert r.status_code == 200


def test_rate_limit_can_be_disabled_via_env(client, monkeypatch):
    """RATE_LIMIT_ENABLED=false overrides RATE_LIMIT_PER_MINUTE."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    for _ in range(10):
        r = client.get("/risk/findings")
        assert r.status_code == 200


def test_rate_limit_zero_disables(client, monkeypatch):
    """RATE_LIMIT_PER_MINUTE=0 disables rate limiting."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    for _ in range(15):
        r = client.get("/risk/findings")
        assert r.status_code == 200


# ===========================================================================
# Combined auth + rate limiting
# ===========================================================================


def test_auth_and_rate_limit_combined(client, monkeypatch):
    """Both enabled: rate limiting is outermost (runs before auth), which
    protects the auth endpoint itself from brute-force key guessing.

    Request flow: RateLimit → Auth → CORS → handler.
    So every request — authenticated or not — consumes rate-limit budget.
    This is the secure edge pattern: an attacker cannot brute-force X-API-Key
    beyond the per-IP rate limit.
    """
    monkeypatch.setenv("VAULTWATCH_API_KEY", "secret-key-123")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    # 3 unauthenticated requests: within rate limit → all 401 (auth rejection).
    for _ in range(3):
        r = client.get("/risk/findings")
        assert r.status_code == 401, f"expected 401, got {r.status_code}"
    # 4th request — even with the CORRECT key — is 429 (rate limit exceeded).
    # This proves rate limiting protects the auth surface from brute force.
    r4 = client.get("/risk/findings", headers={"X-API-Key": "secret-key-123"})
    assert r4.status_code == 429
    assert r4.json()["detail"] == "Rate limit exceeded"
