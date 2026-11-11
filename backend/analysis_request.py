"""Shared request construction and offline, per-request Free-tier admission check."""

import base64
from functools import lru_cache
import hashlib
import gzip
import json
from pathlib import Path

import tiktoken

from schemas import AnalysisResult

MAX_INPUT_TOKENS = 4500
MAX_COMPLETION_TOKENS = 2000
CHAT_OVERHEAD_TOKENS = 256
FREE_TPM = 8000
TOKEN_HEADROOM = FREE_TPM - MAX_INPUT_TOKENS - MAX_COMPLETION_TOKENS
BUDGET_ERROR = (
    "Resume and job description exceed the local Free-tier token budget. "
    "Shorten the resume or job description and try again. No analysis was sent."
)
GPT_OSS_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}
TOKENIZER_PATH = Path(__file__).with_name('tokenizer_data') / 'o200k_base.tiktoken.gz'
TOKENIZER_SHA256 = '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'


class RequestBudgetExceeded(Exception):
    pass


class TokenizerUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def text_tokenizer():
    """GPT-OSS ordinary-text BPE; never downloads files or uses a shared cache.

    Pattern/ranks from MIT-licensed tiktoken's o200k_base, also used by
    o200k_harmony. Treat special-looking user strings as ordinary data.
    """
    try:
        data = gzip.decompress(TOKENIZER_PATH.read_bytes())
        if hashlib.sha256(data).hexdigest() != TOKENIZER_SHA256:
            raise ValueError()
        ranks = {base64.b64decode(token): int(rank) for token, rank in
                 (line.split() for line in data.splitlines())}
        pattern = '|'.join([
            r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
            r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
            r"\p{N}{1,3}", r" ?[^\s\p{L}\p{N}]+[\r\n/]*", r"\s*[\r\n]+", r"\s+(?!\S)", r"\s+",
        ])
        return tiktoken.Encoding(name='gpt_oss_ordinary_text', pat_str=pattern,
                                 mergeable_ranks=ranks, special_tokens={})
    except Exception:
        raise TokenizerUnavailable() from None


def request_parameters(prompt: str, model: str) -> dict:
    """One definition for both preflight counting and the actual SDK request."""
    return {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are a resume analysis assistant. Always respond with valid JSON only.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.3,
        'max_completion_tokens': MAX_COMPLETION_TOKENS,
        'reasoning_effort': 'low',
        'include_reasoning': False,
        'stream': False,
        'response_format': {
            'type': 'json_schema',
            'json_schema': {'name': 'resume_analysis', 'strict': True,
                            'schema': AnalysisResult.provider_schema()},
        },
    }


def estimated_input_tokens(prompt: str, model: str) -> int:
    # Count all request fields, including both schemas (prompt and response_format),
    # roles and Unicode content. JSON wire text is a conservative proxy, not Groq's
    # private chat template. Extra padding covers chat framing/hidden instructions.
    serialized = json.dumps(request_parameters(prompt, model), ensure_ascii=False)
    if model in GPT_OSS_MODELS:
        count = len(text_tokenizer().encode_ordinary(serialized))
    else:
        # Unknown overrides must not inherit a supposedly exact GPT-OSS estimate.
        count = len(serialized.encode('utf-8'))
    return count + CHAT_OVERHEAD_TOKENS


def validate_request_budget(prompt: str, model: str) -> int:
    estimate = estimated_input_tokens(prompt, model)
    if estimate > MAX_INPUT_TOKENS:
        raise RequestBudgetExceeded()
    return estimate
