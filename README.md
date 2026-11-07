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
`http://localhost:8000/analyze`. CORS allows `http://localhost:5173` and
`http://localhost:3000`; deployment URLs still need configuration.
Interactive API documentation is at `http://localhost:8000/docs`.

The backend starts without a key, allowing validation and tests to run. A valid
analysis request without a configured key receives HTTP 503. `/health` reports
key presence only; it does not verify credentials, quota, or model availability.
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
| 502 | Provider request failed or provider output violated the contract |
| 503 | Provider configuration is missing |

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

The provider is constructed lazily, uses the existing model with an asynchronous
SDK call, a 30-second SDK timeout, and no automatic retries. Tests override
`provider.get_provider` through FastAPI dependency injection. No provider key or
network connection is required for the tests.

## Checks

From the repository root:

```sh
backend/venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npm run build
```

The 40 backend tests generate synthetic PDFs and use a stub provider with network
connections blocked. They cover input boundaries, extraction, encryption,
validation failures, output types, sanitized errors, missing configuration,
OpenAPI, bounded reads, and resource cleanup. The installed test client currently
emits an `httpx` deprecation warning; tests still pass.

Live provider quality/availability, browser end-to-end interaction, deployment
configuration, authentication/rate limiting, and more polished frontend error and
input handling remain outside this reliability milestone.
