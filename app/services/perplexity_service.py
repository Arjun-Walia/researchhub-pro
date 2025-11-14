"""Perplexity API integration helpers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class PerplexityValidationError(Exception):
    """Raised when a Perplexity API key cannot be validated."""

    def __init__(self, message: str, reason: str = 'validation_failed'):
        super().__init__(message)
        self.reason = reason


@dataclass
class PerplexityValidationResult:
    """Lightweight result describing a Perplexity validation attempt."""

    status: str
    models_detected: int = 0
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize validation result for JSON responses."""
        return {
            'status': self.status,
            'models_detected': self.models_detected,
            'raw': self.raw or {}
        }


class PerplexityService:
    """Wrapper for Perplexity API validation flow."""

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://api.perplexity.ai',
        timeout: int = 8,
        validate: bool = True
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/') if base_url else 'https://api.perplexity.ai'
        self.timeout = timeout
        self.validate_remote = validate

    def validate_key(self) -> PerplexityValidationResult:
        """Validate the configured API key with Perplexity's models endpoint."""
        if not self.api_key:
            raise PerplexityValidationError('Perplexity API key is required for validation.')

        if not self.validate_remote:
            logger.debug('Skipping Perplexity validation (configuration disabled).')
            return PerplexityValidationResult(status='linked', models_detected=0)

        endpoint = f"{self.base_url}/models"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }

        try:
            response = requests.get(endpoint, headers=headers, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            logger.warning('Perplexity validation timed out: %s', exc)
            raise PerplexityValidationError('Perplexity validation timed out. Please try again.', reason='network') from exc
        except requests.exceptions.RequestException as exc:
            logger.error('Perplexity validation request failed: %s', exc)
            raise PerplexityValidationError('Unable to reach Perplexity. Check your network and try again.', reason='network') from exc

        if response.status_code == 401:
            raise PerplexityValidationError('Perplexity rejected the API key. Double-check and try again.', reason='invalid_credentials')

        if response.status_code >= 400:
            logger.error('Perplexity responded with %s: %s', response.status_code, response.text[:200])
            raise PerplexityValidationError('Perplexity could not validate the key right now. Please retry shortly.', reason='api_error')

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        models = payload.get('data') or payload.get('models') or []
        if isinstance(models, dict):
            models = list(models.values())
        if not isinstance(models, list):
            models = []

        return PerplexityValidationResult(
            status='linked',
            models_detected=len(models),
            raw=payload if isinstance(payload, dict) else {}
        )
