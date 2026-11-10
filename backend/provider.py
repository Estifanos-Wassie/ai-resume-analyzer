"""Lazy provider boundary; importing the application requires no credentials."""

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math

import anyio
import httpx
from fastapi import Request
from groq import AsyncGroq, APIConnectionError, APIStatusError, APITimeoutError

from config import Settings
from operations import logger
from schemas import AnalysisResult

Provider = Callable[[str], Awaitable[str | None]]

# The SDK's debug logs include request bodies and exception details.
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("groq._base_client").setLevel(logging.WARNING)


class ProviderNotConfigured(Exception):
    pass


class GroqProvider:
    """One lazy async client per application lifespan, shared across requests."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._closed = False

    async def __call__(self, prompt: str) -> str | None:
        if self._closed:
            raise ProviderNotConfigured()
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not api_key:
                raise ProviderNotConfigured()
            # No await before assignment: concurrent calls on this loop share one client.
            self._client = AsyncGroq(
                api_key=api_key,
                timeout=httpx.Timeout(
                    self.settings.provider_timeout_seconds,
                    connect=min(5.0, self.settings.provider_timeout_seconds),
                    pool=min(5.0, self.settings.provider_timeout_seconds),
                ),
                max_retries=0,
            )
        response = await self._client.chat.completions.create(
            model=self.settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a resume analysis assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_completion_tokens=8192,
            reasoning_effort="low",
            include_reasoning=False,
            stream=False,
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    'name': 'resume_analysis', 'strict': True,
                    'schema': AnalysisResult.provider_schema(),
                },
            },
        )
        return response.choices[0].message.content

    async def close(self):
        self._closed = True
        client, self._client = self._client, None
        if client is not None:
            try:
                # Shield shutdown cleanup from cancellation, but bound it independently.
                with anyio.move_on_after(5.0, shield=True) as scope:
                    await client.close()
                if scope.cancel_called:
                    logger.warning('{"event":"provider_cleanup","outcome":"timeout"}')
            except Exception:
                logger.warning('{"event":"provider_cleanup","outcome":"failed"}')


@dataclass(frozen=True)
class ProviderFailure:
    status_code: int
    detail: str
    category: str
    retry_after: str | None = None


def safe_retry_after(value: str | None) -> str | None:
    """Normalize delta seconds or an HTTP date; never reflect an arbitrary header."""
    if not value or len(value) > 128:
        return None
    value = value.strip()
    if value.isascii() and value.isdecimal() and len(value) <= 10:
        return str(min(int(value), 3600))
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return None
        seconds = math.ceil((date - datetime.now(timezone.utc)).total_seconds())
        return str(max(0, min(seconds, 3600)))
    except (TypeError, ValueError, OverflowError):
        return None


def classify_failure(error: Exception) -> ProviderFailure:
    if isinstance(error, ProviderNotConfigured):
        return ProviderFailure(503, "Analysis is unavailable because the provider is not configured.", "missing_configuration")
    if isinstance(error, (APITimeoutError, TimeoutError)):
        return ProviderFailure(504, "Analysis service timed out. Try again later.", "timeout")
    if isinstance(error, APIStatusError):
        status = error.status_code
        if status == 429:
            return ProviderFailure(503, "Analysis service is temporarily unavailable due to provider rate limiting. Try again later.", "rate_limited", safe_retry_after(error.response.headers.get("retry-after")))
        if status in (401, 403):
            return ProviderFailure(503, "Analysis service is unavailable due to provider configuration.", "authentication")
        body = error.body if isinstance(error.body, dict) else {}
        detail = body.get("error", body)
        code = detail.get("code") if isinstance(detail, dict) else None
        if isinstance(code, str) and code in {"model_not_found", "model_decommissioned", "model_not_available"}:
            return ProviderFailure(503, "Analysis service is unavailable because the configured model is unavailable.", "model_unavailable")
        if status == 404:
            # Status alone cannot distinguish a missing route from model visibility.
            return ProviderFailure(503, "Analysis service is unavailable because the provider endpoint or requested resource could not be found.", "upstream_not_found")
        if status == 408:
            return ProviderFailure(504, "Analysis service timed out. Try again later.", "timeout")
        category = "server_failure" if status >= 500 else "upstream_rejected"
        return ProviderFailure(502, "Analysis provider could not complete the request. Try again later.", category)
    if isinstance(error, APIConnectionError):
        return ProviderFailure(502, "Analysis provider could not be reached. Try again later.", "connection_failure")
    return ProviderFailure(502, "Analysis provider could not complete the request. Try again later.", "unexpected_provider_failure")


async def get_provider(request: Request) -> Provider:
    return request.app.state.provider
