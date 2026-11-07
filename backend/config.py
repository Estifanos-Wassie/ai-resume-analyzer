"""Local configuration only; parsing never contacts the provider."""

from dataclasses import dataclass
import math
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    provider_timeout_seconds: float = 30.0
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")

    def __post_init__(self):
        if not math.isfinite(self.provider_timeout_seconds) or not 1 <= self.provider_timeout_seconds <= 120:
            raise ValueError("PROVIDER_TIMEOUT_SECONDS must be between 1 and 120 seconds.")
        for origin in self.allowed_origins:
            try:
                parsed = urlsplit(origin)
                valid = (
                    parsed.scheme in ("http", "https") and parsed.hostname
                    and not parsed.username and not parsed.password
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and not any(character.isspace() for character in origin)
                    and "*" not in origin
                )
                parsed.port  # Validate port syntax/range without logging the value.
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("ALLOWED_ORIGINS must contain explicit HTTP(S) origins without paths or credentials.")

    @classmethod
    def from_env(cls):
        try:
            timeout = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ValueError("PROVIDER_TIMEOUT_SECONDS must be a number between 1 and 120.") from None
        origins = os.getenv("ALLOWED_ORIGINS")
        return cls(
            provider_timeout_seconds=timeout,
            allowed_origins=cls.allowed_origins if origins is None else tuple(
                dict.fromkeys(origin.strip() for origin in origins.split(",") if origin.strip())
            ),
        )
