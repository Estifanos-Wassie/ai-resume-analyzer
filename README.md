# AI Resume Analyzer

Upload a text-based PDF resume and paste a job description to receive an AI
estimate of fit, strengths, missing skills, and suggestions. The React/Vite UI
calls a FastAPI backend, which extracts PDF text with PyMuPDF and requests feedback
from Groq using `llama-3.3-70b-versatile`.

The match score is an AI estimate, not a validated employer ATS score or a
prediction of hiring outcomes. There is no independently validated scoring rubric.

## Local setup

Verified with Python 3.14.3 and Node 24.21.0. From the repository root:

```sh
python3 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
```

Set `GROQ_API_KEY` in your environment or in an ignored `backend/.env` file;
`backend/.env.example` lists the variable without a credential. Keep credentials
on the backend. In separate terminals:

```sh
cd backend
venv/bin/python -m uvicorn main:app --reload --port 8000
```

```sh
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend currently targets
`http://localhost:8000/analyze`. CORS defaults to `http://localhost:5173` and
`http://localhost:3000`; use `ALLOWED_ORIGINS` for deployment origins. The frontend
API URL still needs separate deployment configuration.
Interactive API documentation is at `http://localhost:8000/docs`.

The backend starts without a key, allowing validation and tests to run. A valid
analysis request without a configured key receives HTTP 503. `/health` is liveness
only and always returns `200 {"status":"alive"}` when the application is running.
`/ready` reports local configuration only: HTTP 200 when a nonempty key is present,
otherwise 503, with `configuration_ready`, `provider_verified: false`, and
`scope: "local_configuration"`. Neither endpoint creates an SDK client or makes
provider calls. Readiness does not verify credentials, quota, connectivity, or
model availability. Configuration changes require an application restart.
Submitting a valid analysis with a key makes an external provider request and may
consume quota or incur charges.

## Input contract

`POST /analyze` accepts multipart fields `file` and `job_description`.

| Input | Inclusive application limit |
| --- | --- |
| Uploaded file | 5 MiB (5,242,880 bytes) |
| PDF pages | 20 |
| Extracted resume text | 50,000 characters, including extracted whitespace |
| Job description | 20,000 characters after trimming surrounding whitespace |

The filename must end in `.pdf`, case-insensitively. The backend also opens and
reads the document as a PDF; filename and MIME type alone are insufficient.
Empty, corrupt, unreadable, encrypted, and password-protected documents are
rejected. Blank and image-only PDFs require a text-based replacement because OCR
is unsupported. Job descriptions must be nonempty after trimming.

Uploads are read in chunks of at most 64 KiB, stopping after at most 5 MiB plus
one byte to detect an oversized file. Inputs exceeding the limits are rejected,
never silently truncated. Validation finishes before the provider is invoked.

**Handler-level checks do not replace server/proxy request-body limits.** The
framework parses multipart uploads before the handler and may spool them to
temporary disk. Configure a total request-body limit at the server or proxy,
allowing space for multipart overhead and the job description. No such deployment
limit is configured in this repository yet.

## Analysis response

Successful responses contain exactly these four required fields:

```json
{
  "match_score": 75,
  "strengths": ["Python project experience"],
  "missing_skills": ["SQL"],
  "suggestions": ["Describe the synthetic project's outcomes"]
}
```

This is an illustrative synthetic response, not a live model result or fallback.
`match_score` must be an integer from 0 through 100. Booleans, strings, fractional
values, and floating-point values such as `75.0` are rejected. Each feedback field
must be an array containing 0–20 strings; each string must contain 1–1,000
characters after trimming. Unknown fields are rejected. FastAPI's response model,
OpenAPI schema, provider prompt, and runtime validation share this contract.

Empty, malformed, incomplete, non-JSON, or schema-invalid provider output fails
with HTTP 502. Markdown-fenced JSON is not raw JSON and is rejected. Invalid
responses never receive fallback scores.

| HTTP status | Meaning |
| --- | --- |
| 400 | Unsupported filename, empty file, corrupt/unreadable PDF, or file-read failure |
| 413 | Upload, page, resume-text, or job-description limit exceeded |
| 422 | Missing/invalid form fields, whitespace-only description, encrypted PDF, or textless PDF |
| 502 | Provider connection/server failure, other rejected upstream request, unexpected provider failure, or invalid analysis output |
| 503 | Missing/invalid provider credentials, denied provider access, unavailable configured model, or provider rate limiting |
| 504 | Total provider deadline, SDK timeout, or upstream HTTP 408 |

Errors use a fixed, sanitized `detail` string, for example:

```json
{"detail": "Analysis provider returned an invalid response. Try again later."}
```

## Data handling and provider boundary

The app does not intentionally persist resumes or extracted text. Uploaded files
are closed even when validation fails; opened PDF documents use context-managed
cleanup. Framework-managed upload spooling may use temporary disk. The selected
file and session feedback remain in browser memory until replaced or the page is
unloaded; there is no database-backed history.

Full extracted resume text and the trimmed description are sent to Groq only after
validation. External provider retention is outside this application's deletion
controls. Use synthetic inputs for demonstrations. Public errors do not include
submitted content, credentials, provider output, or traces. Parser diagnostics and
the SDK's request/exception debug logging are suppressed; do not enable body
logging in deployment infrastructure.

Each application lifespan owns one lazy `AsyncGroq` client. It is constructed on
the first valid analysis with a configured key and reused for subsequent requests.
Completions are awaited, so a pending provider request does not block independent
health requests. The FastAPI lifespan closes the client at shutdown, including
after failed or cancelled requests. Cleanup is shielded from cancellation with a
separate 5-second bound; cleanup failures/timeouts produce only a safe event.

`PROVIDER_TIMEOUT_SECONDS` defaults to 30 seconds and bounds the entire provider
execution, including client construction and the completion call, after input
validation. SDK read/write timeouts use the same value. Connect/pool timeouts are
the smaller of 5 seconds and the configured value. The total deadline cancels
pending provider execution; it does not include upload parsing or PDF extraction.
These asynchronous cancellation bounds assume a responsive event loop.

The SDK normally retries certain failures twice. This application explicitly sets
`max_retries=0` and has no application retry loop: each accepted analysis makes at
most one completion attempt. There are no automatic fallback requests or scores.
The installed SDK interface was checked against Groq's official
[async, retry, timeout, and resource-management documentation](https://github.com/groq/groq-python).

Provider authentication/permission failures (401/403) become service-level 503
responses, without blaming the user's login. A provider 404, or a recognized
`model_not_found`, `model_decommissioned`, or `model_not_available` code, also maps
to 503. Other upstream rejections and provider 5xx/connection failures map to 502;
input-validation status codes remain unchanged. Provider 429 maps to a temporary
503. A valid provider `Retry-After` integer or HTTP date is normalized to integer
seconds between 0 and 3,600; invalid values are omitted. It is exposed through CORS
for browser clients. Provider and total timeouts return sanitized 504 responses.

Every analysis request emits one JSON operational event containing only its
generated request identifier, duration in milliseconds, fixed outcome category,
and HTTP status. The identifier is returned as `X-Request-ID`; caller-supplied
identifiers are ignored. No filenames, submitted text, provider bodies, credentials,
or exception strings/traces are included. This does not configure infrastructure
access/body logging; keep sensitive body logging disabled there too.

Tests override `provider.get_provider` through FastAPI dependency injection or
exercise the real SDK with an in-memory HTTP transport. No provider key or network
connection is required for the tests.

## Configuration

| Variable | Behavior |
| --- | --- |
| `GROQ_API_KEY` | Backend-only credential; absent/blank keeps liveness and validation available but analysis returns 503 |
| `PROVIDER_TIMEOUT_SECONDS` | Finite number from 1 through 120; default 30 |
| `ALLOWED_ORIGINS` | Comma-separated exact HTTP(S) origins; defaults to the two localhost origins when unset |

For deployment, set `ALLOWED_ORIGINS=https://your-frontend.example` or include both
deployment and localhost origins explicitly. A configured list replaces the
defaults; an empty list denies all cross-origin access. Wildcards, credentials,
paths, and malformed origins are rejected at startup with fixed messages.
Credentialed CORS uses only that explicit list; it never allows `*`.

Start from `backend/.env.example` without overwriting an existing `.env`. No
credentials are stored in the example. The model remains
`llama-3.3-70b-versatile`; changing models is outside this milestone.

## Checks

From the repository root:

```sh
backend/venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npm run build
```

The 58 backend tests generate synthetic PDFs and use stubs or mocked SDK transport
with network connections blocked. They cover input boundaries, extraction,
encryption, response validation, sanitized failures/logging, configuration, CORS,
OpenAPI, request-count bounds, SDK timeout settings, and client cleanup. Event-based
concurrency tests hold a provider request pending while health completes and
expire real cancellation scopes deterministically without elapsed-time assertions.
The installed test client currently
emits an `httpx` deprecation warning; tests still pass.

No live provider calls were used to verify this boundary. Real credentials,
model access/availability, quotas, latency, output quality, and external retention
remain unverified. Browser end-to-end interaction, deployment request-body limits,
frontend API URL configuration, application authentication/rate limiting, and more
polished frontend error/input handling remain outside this milestone.
