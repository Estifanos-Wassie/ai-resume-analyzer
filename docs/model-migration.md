# Configurable Groq model migration — 2026-11-10

This records the migration at `b76d9e1`. Its original 8,192-token completion cap
was subsequently replaced with the [Free-tier budget](free-tier-budget.md):
4,500 estimated complete input tokens, 2,000 completion tokens including reasoning,
and 1,500 headroom. The profile/counts below describe the historical migration.
No additional provider request was made.

The backend now reads `GROQ_MODEL` centrally through `Settings`, defaulting to
`openai/gpt-oss-120b` when the variable is absent. Groq remains the provider and the
SDK endpoint remains `https://api.groq.com/openai/v1/chat/completions`; the model's
`openai/` namespace does not select OpenAI's API or require an OpenAI key.

The legacy model's tier retirement motivated the migration. It does not prove the
cause of the original account-specific 404. The [historical diagnosis](provider-404-diagnosis.md)
and [single live-attempt record](live-verification.md) remain historical evidence.
This migration used no provider API requests, including model-list calls. The
cumulative live-analysis count remains one; successful generation with the new
model is unverified.

## Local and deployment configuration

No real `.env` or credential was changed. With `GROQ_MODEL` unset, restart the
backend to select the default. To override, edit your existing backend `.env` or
process environment without replacing other settings:

```dotenv
GROQ_MODEL=openai/gpt-oss-120b
```

`Settings.from_env()` trims surrounding whitespace and rejects explicitly blank,
whitespace-only, internally whitespace-containing, or over-200-character identifiers
with fixed configuration errors that do not echo the value. Invalid configuration
fails startup, even when no key is present. Validation is local syntax validation,
not confirmation of provider availability, account entitlement, or parameter
compatibility. Existing process variables take precedence over dotenv, so an empty
shell variable must be removed or filled rather than relying on a file value.

The backend and deployment examples include the default. Compose forwards
`GROQ_MODEL` at runtime to the backend only. Its `${GROQ_MODEL-openai/gpt-oss-120b}`
expression defaults only when unset: a deliberately blank value reaches central
validation and fails instead of silently selecting a fallback. For an existing
private deployment file, add/update that variable manually, then recreate services:

```sh
docker compose --env-file deploy/.env.private up --build --detach --wait --wait-timeout 180
```

Use the credential-free smoke commands in the [deployment guide](deployment.md)
for nonbillable checks. Model changes require backend restart/recreation; they do
not require a frontend API/schema change. Provider credentials stay backend-only.
An override must support this request profile: strict JSON-schema output, low
reasoning effort, reasoning exclusion, and the token budget. GPT-OSS 20B is covered
as an explicit compatible override in mocked tests. Arbitrary nonblank IDs are not
assumed supported; a provider rejection remains sanitized and is never retried with
a different model or output mode.

## Request profile and response boundary

The installed `groq==1.4.0` signature and request TypedDict support all parameters
below. Tests exercise its real serialization over in-memory HTTP transport.

| Parameter | Value |
| --- | --- |
| `model` | Centrally validated `settings.groq_model` |
| `response_format.type` | `json_schema` |
| `response_format.json_schema.name` | `resume_analysis` |
| `response_format.json_schema.strict` | `true` |
| `max_completion_tokens` | 8,192; replaces deprecated `max_tokens=1024` |
| `reasoning_effort` | `low` |
| `include_reasoning` | `false` |
| `stream` | `false` |
| `temperature` | 0.3, preserved |
| SDK/application automatic retries | 0 / 0, preserved |

Provider-side constrained decoding uses the documented structural schema subset:
all four public fields are required, `match_score` is an integer, feedback fields
are arrays of strings, and extra properties are forbidden. The schema is derived
from `AnalysisResult`, avoiding undocumented provider-side length/range keywords.
The prompt retains the full public schema and bounds; strict Pydantic validation
still enforces score 0–100, genuine integer types, nonempty trimmed strings, up to
20 entries per array, 1–1,000 characters per string, and no unknown properties.
Provider formatting never replaces that validation, and the frontend contract is
unchanged.

The 8,192-token generated-completion budget leaves room for internal reasoning and
final JSON instead of the old 1,024-token allowance. Low effort reduces reasoning
work but does not turn it off. Hiding reasoning is not a zero-reasoning/zero-cost
promise. This cap is below the documented model output limit; it does not guarantee
that feedback at every maximum array/string length can fit. Empty, malformed,
truncated/schema-invalid content is rejected with sanitized 502, without returning
a partial or fabricated analysis and without increasing the budget automatically.

GPT-OSS does not support `reasoning_format`, so it is omitted. Only
`message.content` is read and then validated into the public result; reasoning
metadata is never returned or logged, even if a mocked upstream includes it despite
`include_reasoning=false`. An extra reasoning field inside JSON fails the closed
public schema. The existing provider deadline (30 seconds by default, 1–120
configurable), per-phase timeouts, client lifecycle, and failure mappings remain.
The budget/deadline are bounded policy choices, not measured live quality/latency.

## Official documentation checked

- [Production model catalog](https://console.groq.com/docs/models)
- [Legacy tier retirement and recommended replacements](https://console.groq.com/docs/deprecations)
- [GPT-OSS 120B capabilities and limits](https://console.groq.com/docs/model/openai/gpt-oss-120b)
- [Strict JSON-schema support and schema requirements](https://console.groq.com/docs/structured-outputs)
- [GPT-OSS reasoning controls](https://console.groq.com/docs/reasoning)
- [Chat-completion parameters](https://console.groq.com/docs/api-reference)

## Verification and limitations

Mocked coverage verifies absent/default and explicit model configuration, blank
rejection without SDK construction, actual SDK request parameters, validated
structured results, malformed outputs, reasoning non-disclosure, unchanged
single-attempt failures, deadlines, and cleanup. Existing frontend tests/browser
journeys remain synthetic and never exercise live Groq. No model-list endpoint,
account probe, or new live analysis was called.

Local checks passed: 70 backend tests, 55 frontend tests, ten desktop/mobile
Chromium journeys with the test-only provider, lint, production build, pip check,
Compose static model/blank forwarding checks, actionlint, and local documentation
links. The existing httpx test-client deprecation warning remains. No real local
model override was present, so a backend restart picks the new default without
editing a real `.env`. Hosted CI results are reported separately after observation.

Provider/account availability, quality, reasoning-token usage, latency, billing,
and scoring/hiring validity remain unverified live. The original 404 record and
failure screenshots still concern the legacy model, not GPT-OSS. Existing
[development dependency advisories](verification.md#npm-advisory-review), public
access/usage controls, HTTPS requirements, and the distinction between local and
hosted container verification remain unchanged. Consult the actual CI run for
hosted results rather than treating local mocks as a live integration pass.
