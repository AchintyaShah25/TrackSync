"""All LLM traffic goes through here (CLAUDE.md architecture rule 3, decision 0026)."""

from .chain import AllProvidersDown, LLMChain, build_chain
from .client import ChatResult, LLMError, OpenAICompatClient, Provider, RateLimited, Unavailable
from .embed import embed_query

__all__ = [
    "AllProvidersDown",
    "ChatResult",
    "LLMChain",
    "LLMError",
    "OpenAICompatClient",
    "Provider",
    "RateLimited",
    "Unavailable",
    "build_chain",
    "embed_query",
]
