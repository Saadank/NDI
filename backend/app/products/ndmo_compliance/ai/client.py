"""Provider-agnostic LLM client for the NDMO Compliance product.

Mirrors the Data Quality product's ``ai/client.py`` design, kept NDMO-local so
the product stays self-contained (the same way the glossary has its own
repositories rather than importing DQ's).  Single entrypoint:

    client = get_ndmo_llm_client()
    if client is None: ...            # graceful "AI unavailable" path
    result = await client.call(system=..., user=..., json_mode=False)

``call`` never raises — every failure surfaces as
``LlmCallResult(success=False, error=...)`` so callers always have a clean
fallback.  Two providers are implemented today:

  * ``ollama``    — local HTTP server (default dev provider).
  * ``anthropic`` — Claude via the ``anthropic`` SDK (lazy-imported).

Configuration is read from the environment, preferring NDMO-specific vars and
falling back to the platform's DQ_LLM_* vars so a single LLM config drives both
products:

    NDMO_LLM_PROVIDER  / DQ_LLM_PROVIDER     ollama | anthropic | none
    NDMO_LLM_BASE_URL  / DQ_LLM_BASE_URL     e.g. http://host.docker.internal:11434
    NDMO_LLM_MODEL     / DQ_LLM_MODEL        e.g. qwen2.5-coder:7b | claude-haiku-4-5-...
    NDMO_LLM_API_KEY   / ANTHROPIC_API_KEY   (anthropic only)
    NDMO_LLM_TIMEOUT_S                       default 45
    NDMO_LLM_MAX_OUTPUT_TOKENS               default 600
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type — uniform across providers.
# ---------------------------------------------------------------------------
@dataclass
class LlmCallResult:
    success: bool
    text: str = ""
    parsed_json: Any = None
    error: str | None = None
    latency_ms: int = 0
    model: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt_hash: str | None = None
    response_hash: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Base + provider implementations
# ---------------------------------------------------------------------------
class LlmClient:
    """Base class — subclasses implement ``is_available`` + ``call``."""

    def is_available(self) -> bool:
        raise NotImplementedError

    async def call(
        self, *, system: str, user: str, json_mode: bool = False,
        max_tokens: int | None = None, timeout_s: float | None = None,
        temperature: float = 0.2,
    ) -> LlmCallResult:
        raise NotImplementedError


class OllamaClient(LlmClient):
    """Local Ollama via its HTTP API (``/api/chat``)."""

    NUM_CTX = 8192

    def __init__(self, base_url: str, model: str, default_timeout_s: float = 45.0,
                 default_max_tokens: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_timeout_s = default_timeout_s
        self.default_max_tokens = default_max_tokens

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=3.0) as c:
                return c.get(f"{self.base_url}/api/tags").status_code == 200
        except httpx.HTTPError as e:
            logger.debug("Ollama tags probe failed: %s", e)
            return False

    async def call(
        self, *, system: str, user: str, json_mode: bool = False,
        max_tokens: int | None = None, timeout_s: float | None = None,
        temperature: float = 0.2,
    ) -> LlmCallResult:
        timeout = timeout_s if timeout_s is not None else self.default_timeout_s
        max_t = max_tokens if max_tokens is not None else self.default_max_tokens
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_t, "num_ctx": self.NUM_CTX},
        }
        if json_mode:
            body["format"] = "json"

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=body)
                latency_ms = int((time.monotonic() - t0) * 1000)
                if resp.status_code != 200:
                    return LlmCallResult(success=False, error=f"http {resp.status_code}: {resp.text[:200]}",
                                         latency_ms=latency_ms, model=self.model)
                data = resp.json()
        except httpx.TimeoutException:
            return LlmCallResult(success=False, error=f"timeout after {timeout}s",
                                 latency_ms=int((time.monotonic() - t0) * 1000), model=self.model)
        except httpx.HTTPError as e:
            return LlmCallResult(success=False, error=f"http error: {e}",
                                 latency_ms=int((time.monotonic() - t0) * 1000), model=self.model)

        text = ((data.get("message") or {}).get("content") or "").strip()
        parsed = None
        if json_mode and text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
        return LlmCallResult(
            success=bool(text), text=text, parsed_json=parsed,
            error=None if text else "empty completion",
            latency_ms=latency_ms, model=self.model,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            prompt_hash=_sha(system + "\n" + user),
            response_hash=_sha(text) if text else None,
            raw=data,
        )


class AnthropicClient(LlmClient):
    """Claude via the ``anthropic`` SDK (lazy-imported so the module stays
    importable without the dependency or a key)."""

    def __init__(self, api_key: str, model: str, default_timeout_s: float = 45.0,
                 default_max_tokens: int = 600) -> None:
        self.api_key = api_key
        self.model = model
        self.default_timeout_s = default_timeout_s
        self.default_max_tokens = default_max_tokens

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def call(
        self, *, system: str, user: str, json_mode: bool = False,
        max_tokens: int | None = None, timeout_s: float | None = None,
        temperature: float = 0.2,
    ) -> LlmCallResult:
        max_t = max_tokens if max_tokens is not None else self.default_max_tokens
        timeout = timeout_s if timeout_s is not None else self.default_timeout_s
        t0 = time.monotonic()
        try:
            from anthropic import AsyncAnthropic
        except ModuleNotFoundError:
            return LlmCallResult(success=False, error="anthropic SDK not installed", model=self.model)
        try:
            client = AsyncAnthropic(api_key=self.api_key, timeout=timeout)
            resp = await client.messages.create(
                model=self.model, max_tokens=max_t, temperature=temperature,
                system=system, messages=[{"role": "user", "content": user}],
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ).strip()
            usage = getattr(resp, "usage", None)
            return LlmCallResult(
                success=bool(text), text=text, error=None if text else "empty completion",
                latency_ms=latency_ms, model=self.model,
                input_tokens=getattr(usage, "input_tokens", None) if usage else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage else None,
                prompt_hash=_sha(system + "\n" + user),
                response_hash=_sha(text) if text else None,
            )
        except Exception as e:  # noqa: BLE001 — never raise out of the client
            return LlmCallResult(success=False, error=f"anthropic error: {e}",
                                 latency_ms=int((time.monotonic() - t0) * 1000), model=self.model)


# ---------------------------------------------------------------------------
# Factory — config from the environment.
# ---------------------------------------------------------------------------
def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


@lru_cache(maxsize=1)
def get_ndmo_llm_client() -> LlmClient | None:
    """Return the configured LLM client, or ``None`` when none is wired
    (callers branch to their no-LLM fallback)."""
    provider = (_env("NDMO_LLM_PROVIDER", "DQ_LLM_PROVIDER", default="") or "").lower().strip()
    if provider in ("", "none", "disabled"):
        return None

    timeout = float(_env("NDMO_LLM_TIMEOUT_S", default="45") or "45")
    max_tokens = int(_env("NDMO_LLM_MAX_OUTPUT_TOKENS", default="600") or "600")

    if provider == "ollama":
        base_url = _env("NDMO_LLM_BASE_URL", "DQ_LLM_BASE_URL")
        model = _env("NDMO_LLM_MODEL", "DQ_LLM_MODEL")
        if not base_url or not model:
            logger.warning("NDMO LLM provider=ollama but base_url/model missing — AI disabled")
            return None
        return OllamaClient(base_url, model, timeout, max_tokens)

    if provider == "anthropic":
        api_key = _env("NDMO_LLM_API_KEY", "ANTHROPIC_API_KEY")
        model = _env("NDMO_LLM_MODEL", "DQ_LLM_MODEL", default="claude-haiku-4-5-20251001")
        if not api_key:
            logger.warning("NDMO LLM provider=anthropic but no API key — AI disabled")
            return None
        return AnthropicClient(api_key, model or "claude-haiku-4-5-20251001", timeout, max_tokens)

    logger.warning("Unknown NDMO LLM provider=%r — AI disabled", provider)
    return None


def is_ndmo_llm_available() -> bool:
    return get_ndmo_llm_client() is not None
