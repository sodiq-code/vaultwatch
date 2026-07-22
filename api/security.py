"""VaultWatch API security — API-key auth + per-IP rate limiting.

Two Starlette middlewares, both dependency-free (no extra packages beyond the
existing FastAPI/Starlette stack), both env-gated and read at request time so
tests can toggle them via ``monkeypatch.setenv`` without re-importing.

AuthMiddleware
    • Header: ``X-API-Key``
    • Enabled when ``VAULTWATCH_API_KEY`` env var is set (non-empty).
      Disabled (open) when unset/empty — dev + test mode, so the existing
      261-test suite is unaffected.
    • Public paths exempt: ``/health``, ``/docs``, ``/redoc``, ``/openapi.json``,
      ``/metrics/spans``.
    • On failure: ``401 Unauthorized`` with ``WWW-Authenticate: X-API-Key``.

RateLimitMiddleware
    • Per-IP sliding-window counter (in-memory, process-local).
    • Config: ``RATE_LIMIT_PER_MINUTE`` (default ``0`` = disabled).
      ``RATE_LIMIT_ENABLED=false`` also disables.
    • Public paths exempt (same allowlist as auth).
    • On exceed: ``429 Too Many Requests`` with ``Retry-After`` header.

Production deployment sets both env vars::

    VAULTWATCH_API_KEY=<32-byte secret>
    RATE_LIMIT_PER_MINUTE=60

Design notes
------------
* Config is read on EVERY request (not at import) so monkeypatch works in tests
  and operators can change limits without a restart.
* The rate-limit store is a module-level dict keyed by ``(ip, window_start)``
  so it can be reset between tests via ``reset_rate_limiter()``.
* Both middlewares are additive — they sit AFTER the CORS middleware so CORS
  preflight (OPTIONS) still works for browser clients.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections import defaultdict
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("vaultwatch.api.security")

# ---------------------------------------------------------------------------
# Public-path allowlist — exempt from both auth and rate limiting
# ---------------------------------------------------------------------------
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics/spans",
    }
)


def _is_public(path: str) -> bool:
    """True if the path is exempt from auth + rate limiting."""
    return path in PUBLIC_PATHS


def _client_ip(request: Request) -> str:
    """Best-effort client-IP extraction (X-Forwarded-For or direct peer)."""
    # Trust the leftmost X-Forwarded-For entry when behind a gateway/proxy.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# AuthMiddleware — X-API-Key header check
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseHTTPMiddleware):
    """Require ``X-API-Key`` header when ``VAULTWATCH_API_KEY`` is configured.

    When the env var is unset/empty, auth is disabled (dev/test mode). This
    keeps the existing test suite green without per-test env juggling.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        # OPTIONS (CORS preflight) is always allowed.
        if request.method == "OPTIONS" or _is_public(path):
            return await call_next(request)

        expected = os.getenv("VAULTWATCH_API_KEY", "")
        if not expected:
            # Auth disabled in dev/test — pass through.
            return await call_next(request)

        provided = request.headers.get("x-api-key", "")
        if not provided:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key header"},
                headers={"WWW-Authenticate": "X-API-Key"},
            )
        # Constant-time comparison ONLY — never use ``provided != expected``
        # before this point, because Python's ``!=`` short-circuits on the
        # first mismatched byte and leaks a timing oracle that lets an
        # attacker recover the key byte-by-byte. ``hmac.compare_digest``
        # always compares every byte in constant time regardless of where
        # the first mismatch is, so the auth decision reveals nothing about
        # *how* the supplied key differs from the expected one.
        if not hmac.compare_digest(provided, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
                headers={"WWW-Authenticate": "X-API-Key"},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# RateLimitMiddleware — per-IP sliding window
# ---------------------------------------------------------------------------

# Module-level store: {ip: [(timestamp, ), ...]} — reset-able for tests.
# Using a simple list-per-IP with lazy pruning keeps the implementation
# dependency-free and O(1) amortised per request.
_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_window_seconds = 60


def reset_rate_limiter() -> None:
    """Clear the in-memory rate-limit store. Call between tests for isolation."""
    _rate_store.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter using a sliding 60-second window.

    Enabled when ``RATE_LIMIT_PER_MINUTE`` is a positive int AND
    ``RATE_LIMIT_ENABLED`` is not ``"false"``. Default disabled (0) so the
    existing test suite is unaffected.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        if request.method == "OPTIONS" or _is_public(path):
            return await call_next(request)

        # Read config at request time (tests monkeypatch env vars).
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false":
            return await call_next(request)

        try:
            limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0"))
        except ValueError:
            limit = 0
        if limit <= 0:
            return await call_next(request)

        ip = _client_ip(request)
        now = time.time()
        window = _rate_window_seconds
        cutoff = now - window

        # Lazy prune: drop timestamps outside the window.
        bucket = _rate_store[ip]
        # Trim in-place (filter to recent entries).
        fresh = [ts for ts in bucket if ts > cutoff]
        _rate_store[ip] = fresh

        if len(fresh) >= limit:
            retry_after = max(1, int(window - (now - fresh[0])))
            logger.warning("Rate limit exceeded for %s (%d/%d)", ip, len(fresh), limit)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window,
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Record this request and proceed.
        _rate_store[ip].append(now)
        response = await call_next(request)
        remaining = max(0, limit - len(_rate_store[ip]))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


__all__: Iterable[str] = (
    "AuthMiddleware",
    "RateLimitMiddleware",
    "PUBLIC_PATHS",
    "reset_rate_limiter",
)
