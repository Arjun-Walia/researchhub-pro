"""SerpAPI integration helpers."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.utils.exceptions import ExternalAPIError, RateLimitError

logger = logging.getLogger(__name__)


class SerpAPISearchService:
    """Wrapper around SerpAPI web search."""

    def __init__(self, api_key: Optional[str], engine: str = "google", timeout: int = 12) -> None:
        self.api_key = (api_key or "").strip()
        self.engine = engine
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, num_results: int = 10, search_type: str = "auto") -> Dict[str, Any]:
        if not self.available():
            raise ExternalAPIError("SerpAPI key not configured.")

        params = {
            "engine": self.engine,
            "api_key": self.api_key,
            "q": query,
            "num": max(1, min(num_results, 10)),
        }

        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise ExternalAPIError("SerpAPI request timed out.") from exc
        except requests.exceptions.RequestException as exc:
            raise ExternalAPIError("Unable to reach SerpAPI.") from exc

        if response.status_code == 429:
            raise RateLimitError("SerpAPI rate limit reached. Please retry shortly.")

        if response.status_code == 401:
            raise ExternalAPIError("SerpAPI rejected the API key.")

        if response.status_code >= 400:
            logger.error("SerpAPI responded with %s: %s", response.status_code, response.text[:200])
            raise ExternalAPIError("SerpAPI could not complete the search request.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalAPIError("SerpAPI returned an invalid response.") from exc

        items: List[Dict[str, Any]] = []
        organic_results = payload.get("organic_results") or []
        for idx, result in enumerate(organic_results[: num_results]):
            items.append(
                {
                    "id": result.get("position") or f"serpapi-{idx}",
                    "title": result.get("title") or result.get("link") or f"Result {idx + 1}",
                    "url": result.get("link"),
                    "snippet": result.get("snippet") or result.get("excerpt") or "",
                    "author": result.get("source"),
                    "published_date": result.get("date"),
                    "score": result.get("score") or max(0.3, 0.9 - idx * 0.1),
                    "source": "SerpAPI",
                }
            )

        return {
            "query": query,
            "answer": payload.get("answer_box", {}).get("answer") if isinstance(payload.get("answer_box"), dict) else None,
            "results": items,
            "total_results": len(items),
            "execution_time": payload.get("search_metadata", {}).get("total_time_taken", 0.0),
            "search_type": search_type,
        }
