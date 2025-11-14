"""Perplexity search service (replacing legacy Exa integration)."""
import json
import logging
import time
import hashlib
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional

import requests

from app.utils.exceptions import ExternalAPIError, RateLimitError


logger = logging.getLogger(__name__)


def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with falsy values to avoid API complaints."""
    return {key: value for key, value in payload.items() if value is not None}


def cache_result(ttl: int = 1800):
    """Decorator to cache function results when Redis cache is configured."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.cache:
                return func(self, *args, **kwargs)

            cache_key = self._generate_cache_key(func.__name__, args, kwargs)
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("Perplexity cache hit for %s", func.__name__)
                return cached

            result = func(self, *args, **kwargs)
            try:
                self.cache.set(cache_key, result, ttl=ttl)
            except Exception as exc:  # pragma: no cover - Redis failures shouldn't break flow
                logger.warning("Failed to cache Perplexity response: %s", exc)

            return result

        return wrapper

    return decorator


class PerplexitySearchService:
    """Thin wrapper around Perplexity's chat/completions endpoint for search."""

    def __init__(
        self,
        api_key: Optional[str],
        cache=None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = (api_key or '').strip()
        self.cache = cache
        self.base_url = (base_url or 'https://api.perplexity.ai').rstrip('/')
        self.default_model = default_model or 'sonar-pro'
        self.timeout = timeout
        self.request_count = 0
        self.last_request_time = None

        if not self.api_key:
            logger.warning('Perplexity API key is not configured. Search requests will fail.')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        key_data = f"{func_name}:{args}:{sorted(kwargs.items())}"
        return f"perplexity:{hashlib.md5(key_data.encode()).hexdigest()}"

    def _check_rate_limit(self, max_per_minute: int = 60) -> None:
        now = time.time()
        if self.last_request_time and now - self.last_request_time < 60:
            if self.request_count >= max_per_minute:
                raise RateLimitError('Perplexity rate limit exceeded. Please wait before retrying.')
        else:
            self.request_count = 0

        self.request_count += 1
        self.last_request_time = now

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _parse_citations(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        citations = payload.get('citations')
        if not citations:
            choices = payload.get('choices') or []
            if choices:
                citations = choices[0].get('citations') or choices[0].get('message', {}).get('citations')
        if not citations:
            return []
        if isinstance(citations, dict):
            citations = list(citations.values())
        if not isinstance(citations, list):
            return []
        return citations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @cache_result(ttl=900)
    def search(self, query: str, num_results: int = 10, search_type: str = 'auto', **kwargs) -> Dict[str, Any]:
        if not query:
            raise ExternalAPIError('Query is required for search.')
        if not self.api_key:
            raise ExternalAPIError('Perplexity API key not configured.')

        self._check_rate_limit()

        start = time.time()
        model = kwargs.pop('model', self.default_model)
        top_k = max(1, min(num_results, 20))

        system_prompt = kwargs.pop(
            'system_prompt',
            'You are an AI research analyst. Provide concise answers and cite relevant sources when available.'
        )

        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': query}
            ],
            'top_k': top_k,
            'return_citations': True,
            'stream': False,
            'temperature': kwargs.pop('temperature', 0.2),
            'search_recency_filter': kwargs.pop('recency_filter', None),
            'max_tokens': kwargs.pop('max_tokens', 800)
        }

        url = f'{self.base_url}/chat/completions'

        try:
            response = requests.post(
                url,
                headers=self._headers(),
                json=_clean_payload(payload),
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as exc:
            raise ExternalAPIError('Perplexity timed out while processing the request.') from exc
        except requests.exceptions.RequestException as exc:
            raise ExternalAPIError('Unable to reach Perplexity. Check your network connection.') from exc

        if response.status_code == 429:
            raise RateLimitError('Perplexity rate limit reached. Please retry shortly.')

        if response.status_code == 401:
            raise ExternalAPIError('Perplexity rejected the API key. Double-check the value in Settings and try again.')

        if response.status_code >= 400:
            message = response.text[:200]
            logger.error('Perplexity search failed (%s): %s', response.status_code, message)
            raise ExternalAPIError('Perplexity could not complete the search request.')

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalAPIError('Perplexity returned an invalid response.') from exc

        citations = self._parse_citations(data)
        results: List[Dict[str, Any]] = []
        for index, citation in enumerate(citations[:top_k]):
            if not isinstance(citation, dict):
                continue
            results.append({
                'id': citation.get('id') or citation.get('uuid') or f'citation-{index}',
                'title': citation.get('title') or citation.get('url') or f'Result {index + 1}',
                'url': citation.get('url'),
                'snippet': citation.get('snippet') or citation.get('content') or citation.get('text') or '',
                'author': citation.get('author'),
                'published_date': citation.get('published_at') or citation.get('date'),
                'score': citation.get('score'),
                'source': citation.get('source')
            })

        answer = None
        choices = data.get('choices') or []
        if choices:
            message = choices[0].get('message') or {}
            answer = message.get('content')

        execution_time = time.time() - start

        return {
            'query': query,
            'answer': answer,
            'results': results,
            'total_results': len(results),
            'execution_time': execution_time,
            'search_type': search_type,
            'timestamp': datetime.utcnow().isoformat()
        }

    def clear_cache(self, pattern: str = 'perplexity:*') -> None:
        if not self.cache:
            return
        try:
            keys = self.cache.keys(pattern)
            if keys:
                self.cache.delete(*keys)
        except Exception as exc:  # pragma: no cover - cache failure should not break flow
            logger.warning('Failed to clear Perplexity cache: %s', exc)

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            'total_requests': self.request_count,
            'last_request': self.last_request_time,
            'cache_enabled': self.cache is not None,
            'default_model': self.default_model
        }


# Backwards compatibility for legacy imports
ExaService = PerplexitySearchService
