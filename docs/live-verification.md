# Controlled live verification — 2026-11-07

The subsequent [configurable model migration](model-migration.md) was verified
offline only. This record and its screenshots concern the legacy model; they do
not show a GPT-OSS request or prove the original account-specific 404 cause.

**Outcome: unsuccessful live analysis; safe error handling verified.** Exactly one
outbound Groq analysis request was attempted. It returned HTTP 404. The production
application classified it as `model_unavailable` and returned sanitized HTTP 503.
No score, strengths, missing skills, or suggestions were accepted or fabricated.

**Offline follow-up, 2026-11-10:** [the 404 diagnosis](provider-404-diagnosis.md)
confirmed canonical routing and documented model retirement for free/developer
tiers, with an enterprise exception. The old `model_unavailable` log category was
inferred from status alone. The classifier now keeps unqualified 404s neutral;
the historical observation below is unchanged. No additional provider request
was made, and the model/account settings were not changed.

## What ran

The working tree was clean at application commit `7f9219d` before adding the
synthetic fixtures and this record. `AGENTS.md` was read. A local backend key was
present, checked as a boolean only; its value was never printed or copied into
frontend configuration, artifacts, documentation, or Git.

The actual production FastAPI application and the built React frontend ran locally
on `localhost:8000` and `localhost:3000`. Port 5173 was already occupied and was
left untouched. The existing allowed localhost origin was used; no application
configuration, provider prompt, credentials, or model was changed. The frontend's
public API URL was supplied only to its build process. Production dependency
overrides were empty; the test-provider harness was not imported or started.

A temporary wrapper outside the repository transparently counted real HTTP
transport requests and blocked any second outbound request before network I/O.
It called the original SDK transport for the one permitted request, without
changing the request or substituting a response. A browser-side guard also allowed
only one `/analyze` POST. Neither temporary guard nor browser profile/trace/cache
is committed. SDK `max_retries=0` and no application retry loop were confirmed.
The backend and frontend processes created for this check were stopped afterward.

The browser uploaded [the synthetic PDF](fixtures/resume-synthetic.pdf) and entered
[the matching job description](fixtures/job-description-synthetic.txt). Native
keyboard file selection was exercised. There was no standalone provider probe,
model-list call, separate live API test, second submission, fallback result, or
model/provider switch.

The PDF is 2,049 bytes, one page, and extracts to 1,263 characters. The job
description received through browser multipart serialization is 912 characters.
All are comfortably within the existing limits. The submitted PDF SHA-256 is
`f48e0817c5a99b04b3f9719a79990a5aa8544f7a1725a6ec65a1018f915ae664`.

| Observation | Recorded value |
| --- | --- |
| Configured and requested model | `llama-3.3-70b-versatile` |
| Browser analysis POSTs | 1 |
| Outbound Groq analysis transport attempts | 1 |
| SDK/application automatic retries | 0 / 0 |
| Extra attempts blocked | 0 |
| Provider HTTP status | 404 |
| Application HTTP status | 503 |
| Browser click-to-JSON-response elapsed time | 0.273 seconds |
| Backend operational duration | 232.3 ms |
| Provider transport-to-headers elapsed time | 0.151 seconds |
| Successful analysis schema validity | Not assessable: no success result returned |

The visible error was local, sanitized copy:

> The analysis service is temporarily unavailable. Your inputs are preserved;
> please try again later.

No retry was performed despite that generic UI text. The operator should review
configured-model availability/access before authorizing any future live attempt.
The observed 404 is consistent with the configured model being unavailable or
inaccessible to this key. The status alone does not establish the precise provider
cause. No raw provider error body was recorded, and neither account permissions,
current model inventory, nor billing outcome was independently probed.

## Browser observations and screenshots

The **same live failure state** was captured at a 1280×1000 desktop viewport and,
by resizing the same page without reloading/submitting, at 390×844 mobile width.
These images are live-attempt error screenshots, not successful live feedback:

- [Desktop live-attempt error](assets/live-attempt-error-desktop.png)
- [Mobile-width live-attempt error](assets/live-attempt-error-mobile.png)

The images contain only the synthetic filename/description and sanitized UI copy.
Both layouts had no horizontal document overflow. No result cards existed to test
for clipping. The long description uses ordinary internal textarea scrolling; it
is retained for a manual retry. Privacy and AI-estimate/hiring-limit notices remain
visible near submission. Clear session accurately describes its tab-local scope.

Before submitting the valid inputs, a required-field UI check produced associated
`role="alert"` errors and focused the PDF input, with a visible solid focus outline;
it sent **zero** analysis POSTs. Enter opened the native file chooser, and Tab moved
to the job description. During the one live request, the `role="status"` live region
changed from the analyzing message to the failed/preserved-input message, and the
sanitized failure appeared as an alert. Actual screen-reader speech was not tested.

Success-state focus, score range, all feedback-array constraints, relevance,
unsupported candidate claims, and suggestions encouraging fabricated qualifications
could not be checked live because no feedback was returned. Prior stub-backed
browser tests cover rendering/focus and schema rejection, not real model quality.
Previously generated images under `frontend/test-results/screenshots/` use stubs;
none should be represented as successful live Groq output.

## Scope and remaining limitations

The single attempt verified browser multipart submission, real PDF extraction,
real provider request dispatch with the configured model, and sanitized failure
propagation back to the browser. It did **not** verify successful end-to-end
feedback generation. Even one successful example would establish integration only,
not scoring accuracy, an employer's ATS behavior, or hiring validity.

No runtime code fix was made. The model/configuration were preserved, and no second
live request was spent on diagnostics. Fixture generation/extraction, mocked backend
and frontend regression checks, and the production frontend build are independent
offline evidence. All automated tests and CI continue to use stubs and no provider
credentials.

The [reproducibility/advisory record](verification.md) remains applicable: four
moderate development-tooling findings remain through minimatch 10.2.6 in ESLint;
no unsupported major override was made. Local Docker execution was blocked by the
absent daemon; [hosted CI run 42432107906](https://github.com/Estifanos-Wassie/ai-resume-analyzer/actions/runs/42432107906)
passed the checks and production-container jobs at commit `7f9219d`. That is separate
from this local live attempt and does not verify public deployment or successful
Groq output. The [deployment guide](deployment.md) still requires HTTPS and access/
usage controls before exposing a public billable endpoint. CORS is not authentication.
