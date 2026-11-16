"""OpenAI-compatible chat client over the standard library (no SDK, no new dependency).

Groq and Gemini both expose `/chat/completions` with tool calling. Requests run in a worker
thread (`asyncio.to_thread`) so the event loop stays free. The HTTP layer is an injectable
`Transport`, which is how tests run without the network.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

USER_AGENT = "f1-analytics-api/0.1 (unofficial, non-commercial)"

# (url, headers, body, timeout) -> (status, headers, body)
Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, dict[str, str], bytes]]


class LLMError(Exception):
    """Base for provider failures."""


class RateLimited(LLMError):
    def __init__(self, provider: str, retry_after: float):
        super().__init__(f"{provider} rate limited; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class Unavailable(LLMError):
    """Timeouts, 5xx, auth/config problems: try the next provider."""


class BadResponse(LLMError):
    """The provider answered but not in the expected shape (or rejected the request)."""


def urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, dict[str, str], bytes]:
    # Groq's Cloudflare front rejects urllib's default "Python-urllib/x.y" agent with a
    # 403 (error 1010), so every request names a generic client.
    req = urllib.request.Request(
        url, data=body, headers={"User-Agent": USER_AGENT, **headers}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers.items()) if err.headers else {}, err.read() or b""
    except (urllib.error.URLError, TimeoutError) as err:
        raise Unavailable(f"network error: {err}") from err


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str  # ends with the OpenAI-compatible root, e.g. https://api.groq.com/openai/v1
    api_key: str
    model: str
    timeout_s: float = 20.0


@dataclass
class ChatResult:
    message: dict[str, Any]  # OpenAI-style assistant message (content and/or tool_calls)
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


def _retry_after(headers: dict[str, str], default: float = 30.0) -> float:
    for k, v in headers.items():
        if k.lower() == "retry-after":
            try:
                return max(float(v), 1.0)
            except ValueError:
                return default
    return default


class OpenAICompatClient:
    def __init__(self, provider: Provider, transport: Transport = urllib_transport):
        self.provider = provider
        self._transport = transport

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float = 0.2,
        max_tokens: int = 900,
    ) -> ChatResult:
        p = self.provider
        payload: dict[str, Any] = {
            "model": p.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {p.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = p.base_url.rstrip("/") + "/chat/completions"
        status, resp_headers, raw = await asyncio.to_thread(
            self._transport, url, headers, json.dumps(payload).encode(), p.timeout_s
        )
        if status == 429:
            # The body says which limit (per minute, per day, request too large).
            log.info("llm %s 429: %s", p.name, raw[:300])
            raise RateLimited(p.name, _retry_after(resp_headers))
        if status >= 500 or status in (401, 403, 404):
            # 401/403/404 mean a bad key or model name: a config problem, not the user's.
            log.warning("llm %s returned %s: %s", p.name, status, raw[:300])
            raise Unavailable(f"{p.name} returned {status}")
        if status != 200:
            raise BadResponse(f"{p.name} returned {status}: {raw[:300]!r}")
        try:
            data = json.loads(raw)
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as err:
            raise BadResponse(f"{p.name} sent an unexpected body") from err
        return ChatResult(
            message=message, provider=p.name, model=p.model, usage=data.get("usage") or {}
        )
