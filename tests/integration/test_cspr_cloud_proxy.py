"""Integration tests — CSPR.cloud reverse proxy + leaked-key rotation (Critical Fix 6).

Verifies that:
  1. The leaked CSPR.cloud API key prefix does NOT appear in any tracked
     source file (it was hardcoded in dashboard/src/liveApi.js + 6 Python
     scripts and has been rotated).
  2. The dashboard routes all cspr.cloud REST calls through the FastAPI
     reverse proxy at /api/cspr_cloud/* (in dev) — it never references the
     cspr.cloud REST API host directly and never sends an Authorization header.
  3. All server-side scripts read the key from `CSPR_CLOUD_API_KEY` env var.
  4. The FastAPI proxy (`GET /cspr_cloud/{path}`) correctly forwards the
     request to the cspr.cloud upstream, injecting `Authorization: Bearer
     $CSPR_CLOUD_API_KEY` from env — and forwards the upstream status code,
     body, and content-type verbatim. On upstream failure returns 502/504.
  5. The `GET /cspr_cloud/status` health endpoint reports whether the key is
     set WITHOUT ever echoing the key itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# The leaked key prefix that must NEVER appear in source again. We test for
# the prefix (not the full key) so the test itself doesn't contain the full
# key either. The prefix is built from parts at runtime so this test file
# itself does NOT contain the literal prefix string (otherwise the scan
# would always flag itself).
LEAKED_KEY_PREFIX = "019" + "ef63a-"

# Source file extensions to scan for the leaked key. Excludes binaries,
# lockfiles, and proof artifacts (which are append-only historical records
# not shipped to production).
_SCANNABLE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".md", ".txt", ".yml", ".yaml", ".toml",
    ".example", ".env", ".sh", ".html", ".css", ".ini", ".cfg",
}

# Directories to skip during the leaked-key scan.
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".venv", "venv", ".pytest_cache", ".ruff_cache",
}


def _walk_source_files(root: Path):
    """Yield source files to scan for the leaked key. Skips binaries,
    lockfiles, proof artifacts, and dependency directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            # Also include dotfiles like .env.example
            stem = Path(fname).name
            if ext not in _SCANNABLE_EXTS and not stem.startswith(".env"):
                continue
            # Skip lockfiles (huge, regenerated, not source)
            if fname in {"package-lock.json", "bun.lockb", "yarn.lock", "poetry.lock"}:
                continue
            # Skip WASM binaries + images
            if ext in {".wasm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}:
                continue
            yield Path(dirpath) / fname


# ---------------------------------------------------------------------------
# §1  Leaked-key scan — the rotated key must never appear in source again
# ---------------------------------------------------------------------------


def test_leaked_key_prefix_not_in_any_source_file():
    """The leaked CSPR.cloud key prefix must NOT appear in any tracked
    source file. This is the core regression test for Critical Fix 6."""
    matches = []
    for fpath in _walk_source_files(ROOT):
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        if LEAKED_KEY_PREFIX in text:
            matches.append(str(fpath.relative_to(ROOT)))
    assert not matches, (
        f"Leaked CSPR.cloud key prefix {LEAKED_KEY_PREFIX!r} found in "
        f"{len(matches)} source file(s): {matches}. The key was supposed to "
        f"be rotated out in Critical Fix 6 — replace with "
        f"os.getenv('CSPR_CLOUD_API_KEY', '')."
    )


def test_leaked_key_not_in_dashboard_liveapi():
    """dashboard/src/liveApi.js must NOT contain the leaked key (it was
    browser-exposed — anyone with devtools open could lift it)."""
    liveapi = ROOT / "dashboard" / "src" / "liveApi.js"
    assert liveapi.exists(), "dashboard/src/liveApi.js not found"
    text = liveapi.read_text(encoding="utf-8")
    assert LEAKED_KEY_PREFIX not in text, (
        "dashboard/src/liveApi.js still contains the leaked CSPR.cloud key prefix"
    )
    # Also check no Bearer header is sent from the frontend at all
    assert "Bearer " not in text or "Bearer ${" in text, (
        "dashboard/src/liveApi.js should not hardcode any Bearer tokens — "
        "all cspr.cloud calls must go through the FastAPI proxy which "
        "injects the Authorization header server-side."
    )


def test_dashboard_liveapi_does_not_call_cspr_cloud_rest_directly():
    """dashboard/src/liveApi.js must NOT call api.testnet.cspr.cloud directly.
    All cspr.cloud REST calls must go through /api/cspr_cloud/* (the FastAPI
    reverse proxy)."""
    liveapi = ROOT / "dashboard" / "src" / "liveApi.js"
    text = liveapi.read_text(encoding="utf-8")
    # The Clarity event store (event-store-api-clarity-testnet.make.services)
    # is a public, no-auth API and may be called directly — that's fine.
    # The cspr.cloud REST API (api.testnet.cspr.cloud) requires the Bearer
    # token and MUST be proxied.
    assert "api.testnet.cspr.cloud" not in text, (
        "dashboard/src/liveApi.js calls api.testnet.cspr.cloud directly — "
        "route through /api/cspr_cloud/* instead so the key stays server-side."
    )
    assert "api.mainnet.cspr.cloud" not in text, (
        "dashboard/src/liveApi.js calls api.mainnet.cspr.cloud directly — "
        "route through /api/cspr_cloud/* instead."
    )


def test_dashboard_liveapi_uses_proxy():
    """dashboard/src/liveApi.js must reference the /cspr_cloud/ proxy path."""
    liveapi = ROOT / "dashboard" / "src" / "liveApi.js"
    text = liveapi.read_text(encoding="utf-8")
    assert "/cspr_cloud/" in text, (
        "dashboard/src/liveApi.js should call /cspr_cloud/<path> through the "
        "FastAPI reverse proxy — found no /cspr_cloud/ reference."
    )


# ---------------------------------------------------------------------------
# §2  Server-side scripts read the key from env, not from source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script_rel",
    [
        "scripts/broadcast_interactions.py",
        "scripts/broadcast_transfers.py",
        "scripts/deploy_live.py",
        "scripts/deploy_new_account.py",
        "scripts/broadcast_deploys.py",
        "scripts/verify_contract_entrypoints.py",
    ],
)
def test_script_reads_key_from_env(script_rel):
    """Every server-side script that previously hardcoded the leaked key
    must now read it from CSPR_CLOUD_API_KEY env var."""
    script = ROOT / script_rel
    assert script.exists(), f"{script_rel} not found"
    text = script.read_text(encoding="utf-8")
    assert LEAKED_KEY_PREFIX not in text, (
        f"{script_rel} still contains the leaked key prefix"
    )
    assert "CSPR_CLOUD_API_KEY" in text, (
        f"{script_rel} should read the key from CSPR_CLOUD_API_KEY env var"
    )
    # Verify the actual os.getenv call is present
    assert "os.getenv" in text, (
        f"{script_rel} should use os.getenv('CSPR_CLOUD_API_KEY', '') "
        f"to read the key"
    )


def test_casper_deploy_cjs_no_hardcoded_key():
    """scripts/casper_deploy.cjs must not contain the leaked key (it was
    in a comment example). The auth_token is now passed in via the request
    JSON, sourced from env by the calling Python script."""
    cjs = ROOT / "scripts" / "casper_deploy.cjs"
    text = cjs.read_text(encoding="utf-8")
    assert LEAKED_KEY_PREFIX not in text, (
        "scripts/casper_deploy.cjs still contains the leaked key prefix"
    )


# ---------------------------------------------------------------------------
# §3  FastAPI proxy — /cspr_cloud/status + /cspr_cloud/{path}
# ---------------------------------------------------------------------------

# We import the app lazily inside tests so that env-var patching takes effect
# before the app module is loaded (the upstream URL + timeout are read at
# module-import time). Each test that needs the app patches the env first,
# then imports.


def _import_app():
    """Import the FastAPI app (after env is patched). Force re-import if
    it was already imported so env-var changes take effect."""
    import importlib
    if "api.main" in sys.modules:
        importlib.reload(sys.modules["api.main"])
    import api.main as api_mod
    return api_mod


def test_cspr_cloud_status_endpoint_does_not_leak_key(monkeypatch):
    """GET /cspr_cloud/status must report whether the key is set WITHOUT
    ever echoing the key itself."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "secret-test-key-do-not-leak-12345")
    api_mod = _import_app()
    from fastapi.testclient import TestClient

    client = TestClient(api_mod.app)
    r = client.get("/cspr_cloud/status")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["upstream"] == "https://api.testnet.cspr.cloud"
    # The key must NEVER appear in the response
    assert "secret-test-key-do-not-leak-12345" not in r.text, (
        "/cspr_cloud/status leaked the API key in the response body"
    )
    assert "secret-test-key-do-not-leak-12345" not in str(r.headers), (
        "/cspr_cloud/status leaked the API key in the response headers"
    )


def test_cspr_cloud_status_endpoint_reports_unconfigured(monkeypatch):
    """GET /cspr_cloud/status must report configured=False when the key is unset."""
    monkeypatch.delenv("CSPR_CLOUD_API_KEY", raising=False)
    api_mod = _import_app()
    from fastapi.testclient import TestClient

    client = TestClient(api_mod.app)
    r = client.get("/cspr_cloud/status")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False


def test_cspr_cloud_proxy_get_forwards_with_bearer_header(monkeypatch):
    """GET /cspr_cloud/{path} must inject `Authorization: Bearer $KEY` from
    env when forwarding to the cspr.cloud upstream."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "test-bearer-token-xyz")
    api_mod = _import_app()

    # Mock httpx.AsyncClient so no real network call is made
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"data":[{"block_height":12345}]}'
    mock_resp.headers = {"Content-Type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/blocks?page_size=1")

    assert r.status_code == 200
    assert "block_height" in r.text

    # Verify the upstream was called with the Bearer header injected
    mock_client.get.assert_awaited_once()
    call_args = mock_client.get.call_args
    forwarded_url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    forwarded_headers = call_args.kwargs.get("headers", {})

    assert forwarded_url == "https://api.testnet.cspr.cloud/blocks?page_size=1", (
        f"proxy forwarded to wrong URL: {forwarded_url}"
    )
    assert forwarded_headers.get("Authorization") == "Bearer test-bearer-token-xyz", (
        f"proxy did not inject Bearer header from env: {forwarded_headers}"
    )


def test_cspr_cloud_proxy_get_forwards_without_key_when_unset(monkeypatch):
    """GET /cspr_cloud/{path} must still work without a key (no Authorization
    header sent) — the public cspr.cloud endpoints don't require auth."""
    monkeypatch.delenv("CSPR_CLOUD_API_KEY", raising=False)
    api_mod = _import_app()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"data":[]}'
    mock_resp.headers = {"Content-Type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/blocks?page_size=1")

    assert r.status_code == 200
    call_args = mock_client.get.call_args
    forwarded_headers = call_args.kwargs.get("headers", {})
    assert "Authorization" not in forwarded_headers, (
        f"proxy sent Authorization header when key was unset: {forwarded_headers}"
    )


def test_cspr_cloud_proxy_get_forwards_status_and_body_verbatim(monkeypatch):
    """The proxy must forward the upstream status code, body, and content-type
    verbatim — including non-200 responses (e.g. 404, 401)."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "k")
    api_mod = _import_app()

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.content = b'{"error":"not found"}'
    mock_resp.headers = {"Content-Type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/nonexistent")

    assert r.status_code == 404, "proxy should forward upstream 404 verbatim"
    assert r.content == b'{"error":"not found"}'
    assert r.headers.get("content-type") == "application/json"


def test_cspr_cloud_proxy_get_forwards_query_string(monkeypatch):
    """The proxy must forward the full query string (page_size, fields, etc.)."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "k")
    api_mod = _import_app()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"[]"
    mock_resp.headers = {"Content-Type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        client.get(
            "/cspr_cloud/accounts/0xabc/deploys?page_size=32&fields=deploy_hash,timestamp,cost,status"
        )

    forwarded_url = mock_client.get.call_args.args[0]
    assert "page_size=32" in forwarded_url
    assert "fields=deploy_hash,timestamp,cost,status" in forwarded_url
    assert "/cspr_cloud/" not in forwarded_url, (
        f"proxy leaked its own path into upstream URL: {forwarded_url}"
    )


def test_cspr_cloud_proxy_get_returns_502_on_upstream_error(monkeypatch):
    """On httpx.HTTPError the proxy must return 502."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "k")
    api_mod = _import_app()

    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/blocks")

    assert r.status_code == 502
    assert "CSPR.cloud" in r.text or "cspr.cloud" in r.text.lower()


def test_cspr_cloud_proxy_get_returns_504_on_timeout(monkeypatch):
    """On httpx.TimeoutException the proxy must return 504."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "k")
    api_mod = _import_app()

    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/blocks")

    assert r.status_code == 504


def test_cspr_cloud_proxy_does_not_echo_key_in_error_responses(monkeypatch):
    """Error responses (502/504) must not echo the API key."""
    monkeypatch.setenv("CSPR_CLOUD_API_KEY", "secret-do-not-leak-999")
    api_mod = _import_app()

    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        from fastapi.testclient import TestClient
        client = TestClient(api_mod.app)
        r = client.get("/cspr_cloud/blocks")

    assert "secret-do-not-leak-999" not in r.text, (
        "proxy leaked the API key in an error response"
    )
    assert "secret-do-not-leak-999" not in str(r.headers), (
        "proxy leaked the API key in error response headers"
    )


# ---------------------------------------------------------------------------
# §4  Vite dev proxy config — /cspr_cloud/* must be proxied to the FastAPI app
# ---------------------------------------------------------------------------


def test_vite_config_proxies_cspr_cloud():
    """dashboard/vite.config.js must proxy /cspr_cloud/* to the FastAPI app
    so the dashboard can call /cspr_cloud/blocks in dev."""
    vite_cfg = ROOT / "dashboard" / "vite.config.js"
    text = vite_cfg.read_text(encoding="utf-8")
    assert "/cspr_cloud" in text or "'/cspr_cloud'" in text, (
        "dashboard/vite.config.js must proxy /cspr_cloud/* to the FastAPI app"
    )


def test_env_example_documents_key_without_leaking():
    """The .env.example must document CSPR_CLOUD_API_KEY with a placeholder,
    not a real key."""
    env_example = ROOT / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "CSPR_CLOUD_API_KEY=" in text
    assert LEAKED_KEY_PREFIX not in text, (
        ".env.example contains the leaked key prefix"
    )
    # The value after the = should be a placeholder, not a real key
    for line in text.splitlines():
        if line.startswith("CSPR_CLOUD_API_KEY=") and not line.strip().startswith("#"):
            value = line.split("=", 1)[1].strip()
            assert value != "", "CSPR_CLOUD_API_KEY value should be a placeholder"
            assert LEAKED_KEY_PREFIX not in value, (
                ".env.example CSPR_CLOUD_API_KEY value contains the leaked key"
            )
