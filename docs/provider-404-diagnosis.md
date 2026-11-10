# Provider 404 diagnosis — 2026-11-10

The repository was clean at `3eaf2bf`; the prior README/preferences work and live
verification were already published. This follow-up made **zero provider API
requests**, including model-list/retrieve calls. Only local source/configuration,
the existing safe ledger/guard, mocked SDK transport, and public documentation were
used. The cumulative live analysis request count remains **one**.

## Evidence and conclusion

| Question | Evidence | Conclusion |
| --- | --- | --- |
| Which model was requested? | Application source and prior safe ledger both name `llama-3.3-70b-versatile` | No spelling mismatch or model switch was found. |
| Was the route wrong? | SDK 1.4.0 defaults to origin `https://api.groq.com` and appends `/openai/v1/chat/completions`. The historical guard allowed only that HTTPS host/path before counting the request. | The recorded request used the canonical route; no application routing defect was found. |
| Was there a base-URL override? | Presence-only local review found none in the process environment or backend `.env`; the live guard independently constrained the historical request. | No evidence of an override causing the recorded 404. Current configuration alone is not a historical environment snapshot. |
| Is the model generally available? | Groq's current model catalog labels it Enterprise; its deprecation notice retired free/developer access on August 16, 2026, exempting enterprise committed-spend contracts. | Tier/model entitlement is the leading explanation, conditional on the key's unknown account tier. |
| Does 404 prove a permissions block? | Groq documents ordinary organization/project model-permission blocks as 403. The recorded response was 404; no provider body/code was retained. | Neither a particular permissions block nor invalid credentials is established by this evidence. |

Official sources reviewed:

- [Chat completion API route](https://console.groq.com/docs/api-reference)
- [August 16, 2026 deprecation and enterprise exception](https://console.groq.com/docs/deprecations)
- [Current model catalog](https://console.groq.com/docs/models) and
  [Llama 3.3 70B model page](https://console.groq.com/docs/model/llama-3.3-70b-versatile)
- [Organization/project model permissions](https://console.groq.com/docs/model-permissions)

The listing is not proof that every account can use this model. If the key belongs
to a free/developer organization, the documented retirement explains why continued
use is unsupported. If it belongs to an exempt enterprise organization, entitlement
or another upstream issue still needs account-specific evidence. No replacement
model was chosen automatically, and no credentials, routing, or account settings
were changed.

## Configuration precedence and SDK URL construction

`backend/main.py` calls `load_dotenv()` with its default `override=False`. Normal
module startup searches from the calling module's directory for the first `.env`
and then parent directories. Existing process variables, including empty values,
take precedence. `PYTHON_DOTENV_DISABLED=1` skips dotenv loading entirely. The local
backend `.env` had a nonempty key and no base-URL override; only presence/expected-
origin comparisons were inspected, never credential values or arbitrary URLs.

The provider reads `GROQ_API_KEY` lazily from the resulting process environment and
passes it explicitly to `AsyncGroq`. It does not pass `base_url`; SDK 1.4.0 therefore
uses `GROQ_BASE_URL` if present, otherwise `https://api.groq.com`. The completion
method already supplies the full `/openai/v1/chat/completions` path. This SDK
appends that route to a base path: setting the base to an OpenAI-style
`https://api.groq.com/openai/v1` would duplicate `/openai/v1`. Mocked transport tests
reproduce that configuration pitfall; it was **not observed in the live attempt**.
A deliberate custom gateway may have its own prefix, so the app does not silently
rewrite overrides or force a different endpoint.

Compose interpolates its explicit environment values from the selected environment
file and shell. The backend service declares only key, deadline, and allowed
origins; it does not forward `GROQ_BASE_URL`. Adding a variable to the Compose
interpolation file alone does not pass it into the container. The production image
also disables dotenv and excludes real environment files. Frontend
`VITE_API_BASE_URL` selects the local application API, not Groq's SDK base URL.

## Confirmed diagnostic defect and focused correction

The earlier classifier treated **every upstream 404** as `model_unavailable` even
without a model-specific error code. The historical log category was therefore an
application inference, not independent confirmation of the provider's cause.

Now only recognized codes (`model_not_found`, `model_decommissioned`, or
`model_not_available`) produce the model-specific category/message. An unqualified
404 stays service-level HTTP 503 but uses `upstream_not_found` and neutral copy
about the provider endpoint/requested resource. No raw body, unknown error code,
exception text, or submitted content is reflected or logged. Known model errors,
input-validation statuses, response schema, model, timeouts, and zero retries are
preserved. This corrects diagnostic certainty; it does **not** restore model access.

Mocked regression checks cover uncoded/unknown/malformed 404 metadata, model-specific
400/404 codes, exact default/root-override routes, duplicated-prefix behavior, and
process-versus-dotenv precedence. All transports are in-memory and socket connections
are blocked. The full backend suite has 64 passing tests after this change.

## Precisely what remains missing

A definitive account-specific diagnosis requires the organization/project tier and
confirmation of any enterprise committed-spend entitlement for this key, plus its
model permissions. The original request's sanitized machine-readable provider code
would also distinguish causes, but it is absent from the retained evidence. A raw
error body or credential value is not needed and should not be shared. An operator
can review existing account settings/request history without submitting another
analysis; no account-console session was accessed in this follow-up.

Those facts are not inferable from a key's presence, a public model listing, the
old `model_unavailable` category, or HTTP 404 alone. Any model migration or renewed
live verification requires a separately authorized decision. The existing one-
request budget has not been reset.
