"""Provider-agnostic LLM client for the Data Quality product.

Single entrypoint: ``LlmClient.call(system, user, json_mode=True)``. Returns
an ``LlmCallResult`` dataclass with the raw text, parsed JSON (when
``json_mode`` is on), token counts, latency, and a success flag.

Ollama is the only implementation today. The shape stays neutral so we can
add OpenAI / Anthropic / Bedrock later without touching every prompt site.

Design notes:
- Ollama's ``/api/chat`` is preferred over ``/api/generate`` because it
  accepts a structured system + user messages array, matching what every
  other provider expects.
- ``format: "json"`` instructs Ollama to constrain output to valid JSON.
  This is the right knob when the prompt asks for JSON; combined with
  ``temperature: 0.1`` it gives us reliable parseable output.
- Cold-start: the first call after server start has to load the model into
  VRAM (~10–30 s on an RTX 2080). Subsequent calls within
  ``OLLAMA_KEEP_ALIVE`` are warm. We use a generous default timeout (90 s)
  and let callers override.
- Token accounting: ``prompt_eval_count`` and ``eval_count`` from Ollama's
  response map to ``input_tokens`` / ``output_tokens``. Anthropic-specific
  cache token fields stay ``None`` for the Ollama impl; the audit table's
  cache columns will simply be NULL for Ollama-era rows.
- Graceful degradation: when the LLM is unreachable, ``is_available()``
  returns False (one log line at startup) and callers fall back to their
  no-LLM path. No call ever raises out of this module — every failure
  surfaces as ``LlmCallResult(success=False, error=...)``.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type — same shape across providers.
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
    # Anthropic-only — kept on the dataclass so audit logging is uniform.
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    # Used by the audit logger to fingerprint prompts without storing them.
    prompt_hash: str | None = None
    response_hash: str | None = None
    # Extra provider-specific bag (raw response keys we may want later).
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base + Ollama implementation
# ---------------------------------------------------------------------------

class LlmClient:
    """Base class — subclasses implement ``call()``."""

    def is_available(self) -> bool:
        raise NotImplementedError

    async def call(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = True,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        temperature: float = 0.1,
    ) -> LlmCallResult:
        raise NotImplementedError


class OllamaClient(LlmClient):
    """Local Ollama, talking to its HTTP API.

    The base URL points at the Ollama server (default
    ``http://host.docker.internal:11434`` when the API runs inside Docker
    and Ollama runs on the Windows/Mac host).
    """

    def __init__(self, base_url: str, model: str, default_timeout_s: float = 90.0,
                 default_max_tokens: int = 1024) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_timeout_s = default_timeout_s
        self.default_max_tokens = default_max_tokens

    def is_available(self) -> bool:
        """Cheap reachability check — used at startup. We don't cache the
        result because Ollama may go up/down independently of the API."""
        try:
            with httpx.Client(timeout=3.0) as c:
                r = c.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except httpx.HTTPError as e:
            logger.debug("Ollama tags probe failed: %s", e)
            return False

    async def call(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = True,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        temperature: float = 0.1,
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
            "options": {
                "temperature": temperature,
                "num_predict": max_t,
            },
        }
        if json_mode:
            body["format"] = "json"

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=body)
                latency_ms = int((time.monotonic() - t0) * 1000)
                if resp.status_code != 200:
                    return LlmCallResult(
                        success=False,
                        error=f"http {resp.status_code}: {resp.text[:200]}",
                        latency_ms=latency_ms, model=self.model,
                    )
                data = resp.json()
        except httpx.TimeoutException:
            return LlmCallResult(
                success=False, error=f"timeout after {timeout}s",
                latency_ms=int((time.monotonic() - t0) * 1000), model=self.model,
            )
        except httpx.HTTPError as e:
            return LlmCallResult(
                success=False, error=f"http error: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000), model=self.model,
            )
        except json.JSONDecodeError as e:
            return LlmCallResult(
                success=False, error=f"non-JSON wrapper response: {e}",
                latency_ms=int((time.monotonic() - t0) * 1000), model=self.model,
            )

        text = (data.get("message") or {}).get("content") or ""
        parsed: Any = None
        if json_mode and text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Even with format=json Ollama may emit slightly off output
                # for small models. Try a salvage pass.
                parsed = _salvage_json(text)
                if parsed is None:
                    return LlmCallResult(
                        success=False,
                        text=text,
                        error="response not valid JSON",
                        latency_ms=latency_ms, model=self.model,
                        input_tokens=data.get("prompt_eval_count"),
                        output_tokens=data.get("eval_count"),
                        raw=data,
                    )

        return LlmCallResult(
            success=True,
            text=text,
            parsed_json=parsed,
            latency_ms=latency_ms,
            model=self.model,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            raw=data,
        )


def _salvage_json(text: str) -> Any:
    """Last-ditch JSON recovery for small-model outputs that wrap the JSON
    in commentary or code fences. Returns ``None`` if nothing usable."""
    text = text.strip()
    # Strip ```json or ``` fences.
    if "```" in text:
        for chunk in text.split("```"):
            c = chunk.strip()
            if c.startswith("json"):
                c = c[4:].strip()
            if c.startswith("{") or c.startswith("["):
                try:
                    return json.loads(c)
                except json.JSONDecodeError:
                    pass
    # Hunt for the first balanced {...} or [...] block.
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


# ---------------------------------------------------------------------------
# Module singleton — cheap (no SDK loaded until needed).
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm_client() -> LlmClient | None:
    """Return the configured LLM client, or ``None`` when none is wired.

    ``None`` (rather than a broken client) lets callers branch cleanly:
    fuzzy-only matcher path, "AI features unavailable" UI banners, etc.
    """
    settings = get_settings()
    provider = (settings.DQ_LLM_PROVIDER or "").lower().strip()
    if provider in ("", "none", "disabled"):
        return None

    if provider == "ollama":
        if not settings.DQ_LLM_BASE_URL or not settings.DQ_LLM_MODEL:
            logger.warning(
                "DQ_LLM_PROVIDER=ollama but DQ_LLM_BASE_URL or DQ_LLM_MODEL is empty — "
                "LLM features disabled"
            )
            return None
        return OllamaClient(
            base_url=settings.DQ_LLM_BASE_URL,
            model=settings.DQ_LLM_MODEL,
            default_timeout_s=float(settings.DQ_LLM_TIMEOUT_S),
            default_max_tokens=settings.DQ_LLM_MAX_OUTPUT_TOKENS,
        )

    logger.warning("Unknown DQ_LLM_PROVIDER=%r — LLM features disabled", provider)
    return None


def is_llm_available() -> bool:
    """Convenience wrapper for callers that just need the boolean."""
    client = get_llm_client()
    return client is not None
