"""Provider fallback chain with per-provider cooldowns (decision 0026).

Free tiers rate-limit hard. When a provider returns 429 (or is down), the chain moves to
the next one and skips the failed provider until its cooldown ends, so a busy minute on
Groq falls through to Gemini instead of failing the user's question.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..config import Settings
from .client import (
    BadResponse,
    ChatResult,
    OpenAICompatClient,
    Provider,
    RateLimited,
    Transport,
    Unavailable,
    urllib_transport,
)

log = logging.getLogger(__name__)

UNAVAILABLE_COOLDOWN_S = 30.0
MAX_COOLDOWN_S = 300.0

GROQ_URL = "https://api.groq.com/openai/v1"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class AllProvidersDown(Exception):
    def __init__(self, retry_after: float):
        super().__init__("all language model providers are busy or unavailable")
        self.retry_after = retry_after


class LLMChain:
    def __init__(self, clients: list[OpenAICompatClient], clock=time.monotonic):
        self.clients = clients
        self._clock = clock
        self._cooldown_until: dict[str, float] = {}

    @property
    def configured(self) -> bool:
        return bool(self.clients)

    def _cool(self, name: str, seconds: float) -> None:
        self._cooldown_until[name] = self._clock() + min(seconds, MAX_COOLDOWN_S)

    async def chat(self, messages: list[dict[str, Any]], tools=None, **kw) -> ChatResult:
        now = self._clock()
        last_error: Exception | None = None
        for client in self.clients:
            name = client.provider.name
            if self._cooldown_until.get(name, 0.0) > now:
                continue
            try:
                return await client.chat(messages, tools, **kw)
            except RateLimited as err:
                log.info("llm %s rate limited for %.0fs; falling back", name, err.retry_after)
                self._cool(name, err.retry_after)
                last_error = err
            except Unavailable as err:
                log.warning("llm %s unavailable: %s; falling back", name, err)
                self._cool(name, UNAVAILABLE_COOLDOWN_S)
                last_error = err
            except BadResponse as err:
                # Malformed answer: try the next provider, but do not bench this one.
                log.warning("llm %s bad response: %s", name, err)
                last_error = err
        waits = [t - now for t in self._cooldown_until.values() if t > now]
        log.error("all llm providers failed: %s", last_error)
        raise AllProvidersDown(retry_after=max(min(waits, default=30.0), 1.0))


def build_chain(settings: Settings, transport: Transport = urllib_transport) -> LLMChain:
    """Providers from settings, in LLM_CHAIN order, skipping any without an API key."""
    available = {
        "groq": (settings.groq_api_key, GROQ_URL, settings.groq_model),
        "gemini": (settings.gemini_api_key, GEMINI_URL, settings.gemini_model),
    }
    clients = []
    for name in (n.strip().lower() for n in settings.llm_chain.split(",") if n.strip()):
        key, url, model = available.get(name, ("", "", ""))
        if key:
            clients.append(OpenAICompatClient(Provider(name, url, key, model), transport))
    return LLMChain(clients)
