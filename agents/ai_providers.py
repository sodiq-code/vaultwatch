"""
VaultWatch — Multi-Provider AI Client

Provides a unified chat-completion interface that tries multiple AI providers
in priority order:

  1. Groq (primary — fast, low-latency)
  2. OpenRouter (secondary — broad model catalog, free tier available)
  3. Heuristic fallback (no external API — rule-based analysis)

This resilience architecture ensures VaultWatch agents always produce
meaningful output even when a provider is temporarily unavailable
(auth errors, rate limits, network issues). For the DoraHacks Casper
Agentic Buildathon, this demonstrates production-grade reliability.

Usage:
    from agents.ai_providers import MultiProviderClient

    client = MultiProviderClient(
        groq_api_key="gsk_...",
        openrouter_api_key="sk-or-...",  # optional — get free key at openrouter.ai
    )

    result = client.chat_completion(
        model="llama-3.3-70b-versatile",
        messages=[...],
        response_format={"type": "json_object"},
        max_tokens=500,
    )
    # result is a ChatCompletion-like object with .choices[0].message.content

Environment variables:
    GROQ_API_KEY       — Groq API key (primary provider)
    OPENROUTER_API_KEY — OpenRouter API key (secondary, free tier available)
    OPENROUTER_MODEL   — Override the default OpenRouter model
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("vaultwatch.ai_providers")

# ---------------------------------------------------------------------------
# Default model mapping: Groq model → OpenRouter equivalent
# ---------------------------------------------------------------------------
# When Groq is unavailable, we map its model names to OpenRouter equivalents.
# OpenRouter free-tier models (suffix :free) are used by default so the
# secondary path works even without paid credits.

GROQ_TO_OPENROUTER: Dict[str, str] = {
    "llama-3.3-70b-versatile": "meta-llama/llama-3.3-70b-instruct:free",
    "llama3-70b-8192": "meta-llama/llama-3-70b-instruct:free",
    "mixtral-8x7b-32768": "mistralai/mixtral-8x7b-instruct:free",
    "gemma2-9b-it": "google/gemma-2-9b-it:free",
}

DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# ---------------------------------------------------------------------------
# Simple response dataclass mimicking Groq/OpenAI ChatCompletion
# ---------------------------------------------------------------------------


@dataclass
class MockChoiceMessage:
    """Mimics openai.types.chat.ChatCompletionMessage."""

    content: str
    role: str = "assistant"


@dataclass
class MockChoice:
    """Mimics openai.types.chat.Choice."""

    message: MockChoiceMessage
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class MockChatCompletion:
    """Mimics groq.types.chat.ChatCompletion for callers that expect
    .choices[0].message.content pattern."""

    id: str = ""
    choices: List[MockChoice] = field(default_factory=list)
    model: str = ""
    created: int = 0

    @property
    def first_content(self) -> str:
        """Convenience: return the first choice's message content."""
        if self.choices:
            return self.choices[0].message.content
        return ""


# ---------------------------------------------------------------------------
# MultiProviderClient
# ---------------------------------------------------------------------------


class MultiProviderClient:
    """Unified AI chat-completion client with multi-provider resilience.

    Tries providers in priority order:
      1. Groq  (if key provided and accessible)
      2. OpenRouter (if key provided and accessible)
      3. Returns None — caller should use heuristic fallback

    The caller (each VaultWatch agent) still owns its own heuristic
    fallback logic. This client simply gives them more chances to get
    a real AI response before falling back.
    """

    def __init__(
        self,
        groq_api_key: str = "",
        openrouter_api_key: str = "",
        groq_client: Any = None,  # pre-built Groq instance (tests / DI)
    ) -> None:
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
        self._openrouter_model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)

        # Build Groq client if possible
        if groq_client is not None:
            self._groq_client = groq_client
        elif self._groq_key:
            try:
                from groq import Groq

                self._groq_client = Groq(api_key=self._groq_key)
            except Exception as exc:
                logger.warning("Groq SDK init failed: %s", exc)
                self._groq_client = None
        else:
            self._groq_client = None

        self._httpx = httpx.Client(timeout=15.0)

    # -----------------------------------------------------------------------
    # Primary: Groq
    # -----------------------------------------------------------------------

    def _try_groq(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Optional[MockChatCompletion]:
        """Attempt Groq chat completion. Returns MockChatCompletion or None."""
        if not self._groq_client:
            return None

        try:
            resp = self._groq_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
            # Convert Groq response to our MockChatCompletion for uniform access
            content = resp.choices[0].message.content
            return MockChatCompletion(
                id=resp.id or "groq-ok",
                choices=[MockChoice(message=MockChoiceMessage(content=content))],
                model=resp.model or model,
                created=resp.created or int(time.time()),
            )
        except Exception as exc:
            exc_str = str(exc)
            is_auth = any(code in exc_str for code in ["403", "401", "429", "Forbidden", "Unauthorized", "Rate limit"])
            if is_auth:
                logger.warning("Groq auth/infra error, falling back: %s", exc_str[:100])
            else:
                logger.error("Groq call error: %s", exc_str[:100])
            return None

    # -----------------------------------------------------------------------
    # Secondary: OpenRouter
    # -----------------------------------------------------------------------

    def _try_openrouter(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Optional[MockChatCompletion]:
        """Attempt OpenRouter chat completion. Returns MockChatCompletion or None.

        Uses httpx to POST to OpenRouter's OpenAI-compatible endpoint.
        The model is mapped from Groq naming to OpenRouter naming via
        GROQ_TO_OPENROUTER, unless the caller explicitly provides an
        OpenRouter model ID.
        """
        if not self._openrouter_key:
            return None

        # Map Groq model → OpenRouter equivalent
        or_model = self._openrouter_model
        if model in GROQ_TO_OPENROUTER:
            or_model = GROQ_TO_OPENROUTER[model]

        payload: Dict[str, Any] = {
            "model": or_model,
            "messages": messages,
        }
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "response_format" in kwargs:
            # OpenRouter supports response_format for compatible models
            payload["response_format"] = kwargs["response_format"]

        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vaultwatch.io",
            "X-Title": "VaultWatch AI Agent",
        }

        try:
            r = self._httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            if r.status_code != 200:
                logger.warning(
                    "OpenRouter HTTP %d: %s",
                    r.status_code,
                    r.text[:120],
                )
                return None

            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return MockChatCompletion(
                id=data.get("id", "or-ok"),
                choices=[MockChoice(message=MockChoiceMessage(content=content))],
                model=data.get("model", or_model),
                created=data.get("created", int(time.time())),
            )
        except Exception as exc:
            logger.warning("OpenRouter call error: %s", str(exc)[:100])
            return None

    # -----------------------------------------------------------------------
    # Unified interface
    # -----------------------------------------------------------------------

    def chat_completion(
        self,
        model: str = "llama-3.3-70b-versatile",
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Optional[MockChatCompletion]:
        """Try Groq → OpenRouter → return None (heuristic fallback).

        Callers should check the result:
          result = client.chat_completion(...)
          if result is not None:
              content = result.first_content  # or result.choices[0].message.content
          else:
              # Use agent-specific heuristic fallback
        """
        messages = messages or []

        # 1. Try Groq (primary)
        result = self._try_groq(model, messages, **kwargs)
        if result is not None:
            logger.debug("AI response via Groq (model=%s)", model)
            return result

        # 2. Try OpenRouter (secondary)
        result = self._try_openrouter(model, messages, **kwargs)
        if result is not None:
            logger.debug("AI response via OpenRouter (model=%s)", model)
            return result

        # 3. Both failed — caller should use heuristic fallback
        logger.info("All AI providers unavailable — heuristic fallback required")
        return None

    # -----------------------------------------------------------------------
    # Convenience: call and parse JSON response
    # -----------------------------------------------------------------------

    def chat_completion_json(
        self,
        model: str = "llama-3.3-70b-versatile",
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Chat completion that parses the response as JSON.

        Returns parsed dict, or None if:
          - Both providers fail
          - Response is not valid JSON
        """
        result = self.chat_completion(model, messages, **kwargs)
        if result is None:
            return None

        try:
            return json.loads(result.first_content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("AI response not valid JSON: %s", result.first_content[:100])
            return None

    # -----------------------------------------------------------------------
    # Compatibility: property to mimic Groq client for direct callers
    # -----------------------------------------------------------------------

    @property
    def groq_client(self) -> Any:
        """Return the underlying Groq client for backward-compatible
        callers that use client.chat.completions.create() directly."""
        return self._groq_client


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def create_client(
    groq_api_key: str = "",
    openrouter_api_key: str = "",
    groq_client: Any = None,
) -> MultiProviderClient:
    """Convenience factory — reads env vars if keys not provided."""
    return MultiProviderClient(
        groq_api_key=groq_api_key or os.getenv("GROQ_API_KEY", ""),
        openrouter_api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY", ""),
        groq_client=groq_client,
    )
