"""LLM provider protocol and GroqProvider implementation.

GroqProvider uses httpx directly (no SDK) and is injectable for testing.
The API key is read from Settings only — never from user input or returned in responses.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"


@dataclass
class ProviderResult:
    content: str                    # raw JSON string from the LLM
    model_used: str | None = None
    latency_ms: int = 0


@dataclass
class ProviderError:
    code: str                       # timeout | auth | rate_limit | model_not_found | server_error | parse_error
    message: str
    status: int | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Injectable protocol — implement this for any LLM backend."""

    def generate(self, messages: list[dict], *, max_tokens: int = 800,
                 temperature: float = 0.1) -> ProviderResult | ProviderError:
        ...

    @property
    def is_available(self) -> bool:
        ...

    @property
    def model_name(self) -> str | None:
        ...


# ---------------------------------------------------------------------------
# In-memory last-call state (per process — not persisted)
# ---------------------------------------------------------------------------

@dataclass
class ProviderState:
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_failure_code: str | None = None
    available: bool = True


# ---------------------------------------------------------------------------
# Groq provider (httpx, no SDK)
# ---------------------------------------------------------------------------

class GroqProvider:
    """Calls Groq's OpenAI-compatible chat completions endpoint via httpx."""

    def __init__(self, api_key: str, model: str, timeout: float = 20.0,
                 transport: httpx.BaseTransport | None = None):
        self._key = api_key
        self._model = model
        self._timeout = timeout
        self._state = ProviderState()
        self._client = httpx.Client(
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )

    @property
    def is_available(self) -> bool:
        return bool(self._key) and self._state.available

    @property
    def model_name(self) -> str | None:
        return self._model

    @property
    def state(self) -> ProviderState:
        return self._state

    def generate(self, messages: list[dict], *, max_tokens: int = 800,
                 temperature: float = 0.1) -> ProviderResult | ProviderError:
        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        start = time.monotonic()
        result = self._try_once(payload)

        # Retry once on 429 or 5xx
        if isinstance(result, ProviderError) and result.code in ("rate_limit", "server_error"):
            time.sleep(1.5)
            result = self._try_once(payload)

        elapsed = int((time.monotonic() - start) * 1000)

        if isinstance(result, ProviderError):
            self._state.last_failure_at = time.time()
            self._state.last_failure_code = result.code
            if result.code in ("auth", "model_not_found"):
                self._state.available = False
        else:
            result.latency_ms = elapsed
            self._state.last_success_at = time.time()
            self._state.available = True

        return result

    def _try_once(self, payload: dict) -> ProviderResult | ProviderError:
        try:
            resp = self._client.post(GROQ_CHAT_URL, json=payload)
        except httpx.TimeoutException:
            return ProviderError("timeout", "LLM request timed out", None)
        except httpx.RequestError as exc:
            return ProviderError("network", f"Network error: {exc}", None)

        if resp.status_code == 401:
            return ProviderError("auth", "API key is invalid or missing", 401)
        if resp.status_code == 404:
            return ProviderError("model_not_found",
                                 f"Model '{self._model}' not found. Set GROQ_MODEL to a valid model.", 404)
        if resp.status_code == 429:
            return ProviderError("rate_limit", "Groq rate limit exceeded", 429)
        if resp.status_code >= 500:
            return ProviderError("server_error", f"Groq server error {resp.status_code}", resp.status_code)
        if not resp.is_success:
            return ProviderError("http_error", f"HTTP {resp.status_code}", resp.status_code)

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", self._model)
            return ProviderResult(content=content, model_used=model_used)
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            return ProviderError("parse_error", f"Could not parse Groq response: {exc}", None)

    def close(self):
        self._client.close()


# ---------------------------------------------------------------------------
# Fake provider for testing (injectable via test fixtures)
# ---------------------------------------------------------------------------

class FakeProvider:
    """Deterministic fake: returns a configurable response or error."""

    def __init__(self, response_json: str | None = None,
                 error: ProviderError | None = None):
        self._response = response_json
        self._error = error
        self._state = ProviderState()
        self._calls: list[list[dict]] = []

    @property
    def is_available(self) -> bool:
        return self._error is None

    @property
    def model_name(self) -> str | None:
        return "fake-model"

    @property
    def calls(self) -> list[list[dict]]:
        return self._calls

    def generate(self, messages: list[dict], *, max_tokens: int = 800,
                 temperature: float = 0.1) -> ProviderResult | ProviderError:
        self._calls.append(messages)
        if self._error is not None:
            self._state.last_failure_at = time.time()
            self._state.last_failure_code = self._error.code
            return self._error
        self._state.last_success_at = time.time()
        return ProviderResult(content=self._response or "{}", model_used="fake-model", latency_ms=1)


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def make_provider(settings) -> LLMProvider | None:
    """Return a GroqProvider if configured, else None."""
    key = getattr(settings, "groq_api_key", None)
    model = getattr(settings, "groq_model", "openai/gpt-oss-20b")
    timeout = float(getattr(settings, "ai_timeout_seconds", 20))
    if key:
        return GroqProvider(api_key=key, model=model, timeout=timeout)
    return None

