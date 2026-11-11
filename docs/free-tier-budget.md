# Local Free-tier request budget

The user privately confirmed the key-to-console association and Free ($0) status,
with `openai/gpt-oss-120b` limits of 30 requests/minute, 1,000 requests/day,
8,000 tokens/minute and 200,000 tokens/day. No key suffix, account screenshot,
credential, or account identifier is recorded here. This is user-supplied console
evidence, not application or API verification. No new live request is authorized.
The cumulative live-analysis count remains **one**.

## Per-request policy

| Component | Tokens |
| --- | ---: |
| Maximum estimated complete input | 4,500 |
| Completion cap, including reasoning and final JSON | 2,000 |
| Additional unused headroom below 8,000 | 1,500 |

The input estimate tokenizes the complete shared request definition serialized as
Unicode JSON: both messages, all instructions, the full resume and trimmed job
description, the public schema in the prompt, the strict response-format schema,
and other request fields. It adds **256 tokens within the 4,500 input allowance**
for chat framing/provider-internal presentation. Counting JSON keys/syntax is a
conservative proxy, not an exact reconstruction of Groq's private chat template.
The extra 1,500-token margin allows for estimation error; it is not reserved quota.

The completion cap is lowered from 8,192 to **2,000**. Low reasoning effort and
hidden reasoning remain enabled. Reasoning uses generated output even when hidden;
the cap is reserved for reasoning **and** final JSON, not 2,000 final-answer tokens
plus extra reasoning. The prompt requests concise feedback (prefer up to three
items per array, up to 160 characters each). This is guidance; the public schema
still accepts up to 20 items of 1–1,000 characters and integer scores 0–100.
There is no guarantee that maximum-sized feedback or every reasoning trace fits.
Truncated/non-`stop` completions and malformed content fail with sanitized 502,
without partial/fake results, an increased budget, retries or model fallback.

`backend/analysis_request.py` defines fixed admission/output constants and shared
SDK parameters. These are not environment-tunable upward overrides. Model/deadline
configuration is unchanged. No credentials, account, payment or real `.env`
settings were changed. Groq remains the provider; the OpenAI model namespace and
tokenizer do not select OpenAI's API.

## Offline tokenizer and rejection

Pinned `tiktoken==0.14.0` uses bundled, SHA-256-checked o200k vocabulary and the
ordinary-text pattern used by GPT-OSS's `o200k_harmony`. Literal special-token-like
strings cannot introduce control tokens. The compressed vocabulary and MIT license
ship in the container allowlist: no runtime download/cache is needed. Tokenization
runs in a worker thread before invoking the injected provider or constructing its
SDK client. Submitted text/tokenization results are not persisted or logged.
A missing or corrupt vocabulary returns a fixed 503 without contacting Groq.

The same tokenizer covers the compatible 20B override. Unknown model overrides
use a conservative UTF-8-byte estimate plus framing padding rather than claiming
this tokenizer matches them. Such overrides still need separate Free-tier/access/
parameter confirmation; no automatic fallback exists.

Existing PDF/upload/page/character protections remain independent hard ceilings.
Passing them does not imply passing the token budget. An estimated complete input
of 4,500 tokens is admitted; 4,501 is rejected before provider invocation with
HTTP **413**:

```json
{"detail":"Resume and job description exceed the local Free-tier token budget. Shorten the resume or job description and try again. No analysis was sent."}
```

Neither document is silently truncated. The frontend recognizes this exact safe
error and asks users to shorten either input while preserving inputs. Unknown
server details are never displayed.

## Accounting limits and console checks

Groq's [rate-limit documentation](https://console.groq.com/docs/rate-limits)
describes shared organization limits, combined TPM and possible separate input/
output limits, 429 responses and Retry-After. It exempts cached tokens; this check
assumes **no cache discount**. The [chat API reference](https://console.groq.com/docs/api-reference)
defines the completion cap and context budget. The [reasoning documentation](https://console.groq.com/docs/reasoning)
identifies reasoning as output and explains that hiding it changes visibility.
Public documentation does not fully specify the chat limiter's cap-reservation/
refund algorithm or private prompt rendering. Reserving the full cap is our
conservative policy, not a claim about exact provider admission accounting.
The Responses API's explicitly inclusive reasoning cap corroborates the approach;
this application continues to use **chat completions**, not Responses.

There is no organization-wide quota tracker or rate scheduler. Concurrent requests,
other keys/processes or recent usage can exhaust minute/day allowances despite
each request passing locally. RPM/RPD/TPD and remaining quota are not guaranteed.
Exact usage, reasoning/output quality and latency remain unverified live. SDK and
application retries remain zero. Provider 429 maps to sanitized 503 with safe
Retry-After; recovery is manual after the delay and requires fresh authorization
for a verification request. Stop when free limits are exhausted or payment is
required; never upgrade or use paid fallbacks.

Before any future live request, reconfirm the correct organization's **Free ($0)**
current plan at [Billing → Plans](https://console.groq.com/settings/billing/plans),
the model's [Organization Limits](https://console.groq.com/settings/limits) and
**Project → Limits**, plus **Usage**. Project-specific rate restrictions, model
permissions/terms and separate input/output TPM restrictions still need console
review; account-level screenshots alone do not prove them. Never share the key.
Keep the application local; no hosting or paid services are provisioned.

## Offline verification

The updated suite passed 81 backend tests, 56 frontend unit/component tests and
12 desktop/mobile Chromium checks. These include SDK MockTransport requests,
Unicode and exact admission boundaries, missing/corrupt tokenizer data, rejection
before SDK construction, schema-invalid/truncated output, safe errors/logs, and
actual multipart extraction with the test-only provider followed by manual input
shortening. Lint, production build, pip check, credential-free backend startup and
static Compose checks passed. The first browser run exposed an old character-limit
fixture that now exceeded the independent token ceiling; compressible filler now
isolates its original Unicode/CRLF character-boundary assertion. The rerun passed.
The initial local startup smoke needed permission to bind localhost sockets and
passed when rerun with that permission. Local container execution remains
unverified; hosted CI is reported separately after observation.
