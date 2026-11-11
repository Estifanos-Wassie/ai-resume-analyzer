# Offline GPT-OSS text tokenizer

`o200k_base.tiktoken.gz` is a deterministic gzip copy (`mtime=0`) of
<https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken>.
The decompressed SHA-256 is
`446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.

GPT-OSS's `o200k_harmony` uses these ordinary-text ranks and the o200k split
pattern. The pattern in `analysis_request.py` is from pinned tiktoken 0.14.0.
See the [reference tokenizer](https://github.com/openai/gpt-oss/blob/main/gpt_oss/tokenizer.py)
and [tiktoken implementation](https://github.com/openai/tiktoken/blob/0.14.0/tiktoken_ext/openai_public.py).
The accompanying MIT license applies to the vocabulary/pattern. The required
third-party copyright notice is licensing information, not commit attribution.

Runtime reads only this bundled, checksum-verified file; it never downloads a
tokenizer, contacts a model endpoint, or depends on a user's tokenizer cache.
Special-looking submitted strings remain ordinary text. Chat framing and Groq's
internal schema presentation are estimates, not exact token accounting.
