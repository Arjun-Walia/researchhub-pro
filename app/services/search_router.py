"""Search orchestration utilities for cascading across engines."""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.utils.exceptions import ExternalAPIError

logger = logging.getLogger(__name__)


class SearchProvider:
    """Abstract search provider."""

    name: str = "provider"

    def available(self) -> bool:  # pragma: no cover - interface hook
        return True

    def search(
        self,
        query: str,
        num_results: int,
        search_type: str,
        enhance_query: bool,
        **kwargs: Any,
    ) -> Dict[str, Any]:  # pragma: no cover - interface hook
        raise NotImplementedError


class OpenAISearchProvider(SearchProvider):
    """Lightweight provider that leverages OpenAI-powered suggestions."""

    name = "openai"

    def __init__(self, ai_service):
        self.ai_service = ai_service

    def available(self) -> bool:
        return bool(getattr(self.ai_service, "openai_key", None))

    def search(
        self,
        query: str,
        num_results: int,
        search_type: str,
        enhance_query: bool,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.available():
            raise ExternalAPIError("OpenAI integration is not configured.")

        suggestions = self.ai_service.suggest_related_queries(query, max(3, min(num_results, 8)))
        if not suggestions:
            raise ExternalAPIError("OpenAI did not return related queries.")

        results: List[Dict[str, Any]] = []
        for idx, suggestion in enumerate(suggestions[:num_results]):
            score = max(0.45, 0.85 - idx * 0.08)
            results.append(
                {
                    "id": f"openai-{idx}",
                    "title": suggestion,
                    "url": f"https://www.google.com/search?q={suggestion.replace(' ', '+')}",
                    "snippet": f"OpenAI generated research lead: {suggestion}",
                    "author": "OpenAI Assistant",
                    "published_date": None,
                    "score": score,
                    "source": "OpenAI generated lead",
                }
            )

        return {
            "query": query,
            "answer": None,
            "results": results,
            "total_results": len(results),
            "execution_time": 0.0,
            "search_type": search_type,
        }


class PerplexitySearchProvider(SearchProvider):
    """Provider backed by the Perplexity search service."""

    name = "perplexity"

    def __init__(self, service):
        self.service = service

    def available(self) -> bool:
        return bool(getattr(self.service, "api_key", None))

    def search(
        self,
        query: str,
        num_results: int,
        search_type: str,
        enhance_query: bool,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.available():
            raise ExternalAPIError("Perplexity integration is not configured.")

        return self.service.search(query=query, num_results=num_results, search_type=search_type)


class SerpAPISearchProvider(SearchProvider):
    """Provider backed by SerpAPI for web enrichment."""

    name = "serpapi"

    def __init__(self, service):
        self.service = service

    def available(self) -> bool:
        return bool(self.service and self.service.available())

    def search(
        self,
        query: str,
        num_results: int,
        search_type: str,
        enhance_query: bool,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.available():
            raise ExternalAPIError("SerpAPI integration is not configured.")

        return self.service.search(query=query, num_results=num_results, search_type=search_type)


class SearchOrchestrator:
    """Coordinate multiple providers with graceful fallback."""

    def __init__(
        self,
        providers: List[SearchProvider],
        fallback_enabled: bool,
        fallback_builder,
    ) -> None:
        self.providers = providers
        self.fallback_enabled = fallback_enabled
        self.fallback_builder = fallback_builder

    def search(
        self,
        query: str,
        num_results: int,
        search_type: str,
        enhance_query: bool,
        fallback_reason: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str, List[str], List[Dict[str, str]], bool]:
        attempts: List[str] = []
        errors: List[Dict[str, str]] = []

        for provider in self.providers:
            if not provider.available():
                continue
            attempts.append(provider.name)
            try:
                result = provider.search(
                    query=query,
                    num_results=num_results,
                    search_type=search_type,
                    enhance_query=enhance_query,
                )
                return result, provider.name, attempts, errors, False
            except ExternalAPIError as exc:
                logger.warning("%s provider failed: %s", provider.name, exc)
                errors.append({"provider": provider.name, "message": str(exc)})
                continue

        if self.fallback_enabled and self.fallback_builder:
            fallback = self.fallback_builder(query, num_results, fallback_reason or "All providers unavailable")
            return fallback, "offline-fallback", attempts, errors, True

        raise ExternalAPIError("All search providers failed.")
