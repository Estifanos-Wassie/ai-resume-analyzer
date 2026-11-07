"""Lazy provider boundary; importing the application requires no credentials."""

import logging
import os
from collections.abc import Awaitable, Callable

from groq import AsyncGroq

Provider = Callable[[str], Awaitable[str | None]]

# The SDK's debug logs include request bodies and exception details.
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("groq._base_client").setLevel(logging.WARNING)


class ProviderNotConfigured(Exception):
    pass


async def generate_analysis(prompt: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ProviderNotConfigured()

    async with AsyncGroq(api_key=api_key, timeout=30.0, max_retries=0) as client:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a resume analysis assistant. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content


def get_provider() -> Provider:
    return generate_analysis
