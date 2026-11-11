# Controlled GPT-OSS live verification — 2026-11-10

**Succeeded:** the real local browser → multipart upload → PDF extraction → Groq
→ validated feedback → browser journey completed using `openai/gpt-oss-120b`.
Exactly **one additional** Groq completion request was sent, without retries,
fallbacks or other provider API calls. Including the [historical failed request](live-verification.md),
the cumulative live-analysis count is **two**. This authorization is exhausted.

## Preparation and guard

The working tree was clean at `25549e2`. `AGENTS.md` and the prior private guard/
ledger were inspected; the old ledger recorded one attempt. The user confirmed
the configured key's console association, Free ($0), 30 RPM / 1,000 RPD / 8,000 TPM
/ 200,000 TPD, no custom project limits, and no pending GPT-OSS model terms.
This is user-supplied account-console evidence, not a billing inference from a key
or this successful request. No account-console session was accessed by the agent.

Local comparison confirmed the effective credential matched `backend/.env`, without
printing it. The effective model was `openai/gpt-oss-120b`, no `GROQ_BASE_URL`
override was present, the real provider was active, and dependency overrides were
empty. No credential, real environment file, model, prompt, budget, timeout, billing
setting, account setting or hosting resource was changed for this attempt.

The actual production FastAPI application ran at `localhost:8000`, with the built
React frontend at `localhost:3000` using a process-local public API build URL.
Neither the test server nor a stub provider was active. The existing localhost
origins and 30-second provider deadline were used. Both servers were stopped after
the single submission and capture. Unrelated services were left alone.

A private transport guard outside Git allowed only HTTPS POST to
`api.groq.com/openai/v1/chat/completions`, with the authorized model, strict schema,
low effort, hidden reasoning, 2,000 completion-token cap and SDK retries zero.
It checked the request against the offline-preflight payload hash and counted the
attempt **before network I/O**. Any second request or other provider route,
including model-list calls, would be blocked. Its ledger prevents restarting the
session; no budget reset was performed. A browser guard separately limited
`/analyze` POSTs to one. Neither guard altered the provider result. No additional
attempt was blocked because no extra request was made. Private guards, ledgers,
browser profile/cache and transient inspection files are excluded from Git.

## Fictional input and offline preflight

- [Text-based fictional PDF](fixtures/resume-free-tier-fictional.pdf)
- [Editable fictional resume source](fixtures/resume-free-tier-fictional.txt)
- [Matching fictional job description](fixtures/job-description-free-tier-fictional.txt)

These short fixtures contain no real person's contact, employer, education or
employment details. The resume describes a fictional FastAPI/React task project
with validation and API tests. It explicitly claims no SQL, Docker or professional
experience. The fictional role requires basic SQL and makes Docker optional.

Before startup, the actual input validator and request-building handler were run
locally with a recording-only callable that stopped before network execution.
The complete request passed the local token check. The real transport later
confirmed exact content/parameter agreement with this preflight.

| Input/accounting measurement | Value |
| --- | ---: |
| PDF bytes / pages | 1,547 / 1 |
| Extracted resume characters | 587 |
| Trimmed description characters after multipart CRLF serialization | 392 |
| Local complete-input estimate, including schemas and framing padding | 1,107 tokens |
| Configured completion allowance, reasoning plus final JSON | 2,000 tokens |
| Conservative per-request total | 3,107 tokens |
| Margin below verified 8,000 TPM | 4,893 tokens |

The PDF SHA-256 is
`e2c0e1ef4958f2b682b5bfa3d9b883f75a60c7a44b1439e9ef43c9f91b7f3b80`.
The input estimate is intentionally different from provider accounting; no cache
discount or assumption of remaining organization quota was used.

## Observed live outcome

| Observation | Value |
| --- | --- |
| Requested model | `openai/gpt-oss-120b` |
| Browser analysis POSTs / outbound Groq attempts | 1 / 1 |
| Cumulative live-analysis count | 2 |
| Automatic SDK/application retries / extra attempts blocked | 0 / 0 / 0 |
| Provider / application status | 200 / 200 |
| Application outcome category | `success` |
| Browser click-to-JSON elapsed time | 1.108 seconds |
| Backend operational duration | 1,063.16 ms |
| Transport through response-body observation | 0.871 seconds |
| Provider-reported prompt / completion / total tokens | 754 / 225 / 979 |
| Provider-reported reasoning tokens | 59, included in completion tokens |
| Validated match score | 70, genuine integer within 0–100 |
| Strengths / missing skills / suggestions counts | 3 / 2 / 3 |

FastAPI's strict Pydantic validation and frontend structure validation both passed:
all four expected fields were present, feedback arrays contained trimmed nonempty
strings within documented bounds, and no reasoning field or raw provider metadata
was exposed in the public result. Only allowlisted numeric usage was retained in
private safe diagnostics; no raw provider response or reasoning trace was saved.

## Feedback review and browser observations

Feedback matched Python/FastAPI, React/JavaScript, input validation and API tests to
the fictional role. It identified the deliberately omitted basic SQL skill and
correctly labeled Docker optional. Suggested SQLite and Docker practice projects
were relevant learning tasks. No employment, degree or numeric business outcome
was invented in the displayed result.

Two qualifications matter: describing the candidate as **proficient** infers a
skill level not established by a short project listing. The suggestion to quantify
outcomes, including performance improvements, is generic and not evidence that
improvements occurred. Count actual tests or measure real results before claiming
metrics; never invent them. The fictional fixture and suggestions must not be
presented as the repository author's qualifications.

The same rendered result was inspected at desktop 1280×1000 and mobile-emulated
390×844, by resizing one page without reload or another submission. The feedback
text was identical across sizes. There was no horizontal document overflow or
clipped result card. Narrow-width description text scrolls inside its textarea;
privacy and AI-estimate notices remain readable near submission.

- [Desktop live success screenshot](assets/live-gptoss-fictional-desktop.png)
- [Mobile-width live success screenshot](assets/live-gptoss-fictional-mobile.png)

These images contain synthetic input and **real, validated Groq feedback** from
this request. They differ from the old legacy-model failure screenshots and the
ignored stub-backed browser-test screenshots. Neither image shows credentials,
account details, raw responses or reasoning traces.

Before submission, empty required-field checks announced two alerts and focused
the PDF control without an HTTP POST. Its focus outline was solid. Enter opened
the native file picker and Tab reached the description. During analysis the live
status changed from analyzing to ready, and the feedback heading received focus.
Actual assistive-technology speech and real mobile hardware were not tested.

## Scope and remaining limitations

This verifies one successful local integration example, **not** scoring accuracy,
an employer ATS score, hiring validity, robust model quality, future availability,
remaining shared quota, or a latency guarantee. One response does not establish
the adequacy of the completion budget for larger inputs. The original legacy 404's
exact account-specific cause remains unproven. Its historical diagnosis is intact.

The application remains local and Free-tier only. No billing/account settings,
payment method or hosting changed. Any future live request needs new authorization
and fresh account/model/quota confirmation. The [budget limitations](free-tier-budget.md)
and [development dependency advisories](verification.md#npm-advisory-review) remain.
No public deployment was performed. Local Docker execution remains unverified;
[credential-free hosted CI at `25549e2`](https://github.com/Estifanos-Wassie/ai-resume-analyzer/actions/runs/42929246176)
passed both checks and container smoke tests, independently of this live result.
This task changes documentation and synthetic artifacts only, not runtime code.
The frontend production build, 81 mocked backend tests, 56 frontend tests and lint
passed during this task. Offline fixture/hash/image and local documentation-link
checks also passed. No additional live request was used for those checks.
