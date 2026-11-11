# AI Resume Analyzer

A local web application that compares a text-based PDF resume with a job description
and returns an AI-estimated match score, strengths, missing skills, and suggestions.

The score is an AI estimate—not a validated employer ATS score or hiring prediction.

## Features

- PDF upload through a file picker or drag-and-drop.
- Resume text extraction and input validation before analysis.
- Structured feedback from Groq, validated by the backend before display.
- Accessible forms, loading states, clear errors, and manual retry.
- Session-only analysis history with a clear-session action.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript, CSS |
| Backend | FastAPI, Pydantic, PyMuPDF |
| Analysis | Async Groq SDK, `openai/gpt-oss-120b` |
| Token accounting | Bundled offline GPT-OSS text tokenizer via tiktoken |
| Testing | unittest, Vitest, Testing Library, Playwright |
| Automation | GitHub Actions; Docker Compose and Nginx for local container checks |

Groq hosts the configured model; the application does not use OpenAI's API.

## Local setup

Tested runtimes: **Python 3.14.3** and **Node.js 24.21.0**, with pip 26.0 and
npm 11.19.0. Version files are provided in `.python-version` and `.nvmrc`.

From the repository root, install dependencies:

```sh
python3 -m venv backend/venv
backend/venv/bin/python -m pip install pip==26.0
backend/venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
```

Create local configuration files only if they do not already exist:

```sh
test -e backend/.env || cp backend/.env.example backend/.env
test -e frontend/.env || cp frontend/.env.example frontend/.env
```

Set `GROQ_API_KEY` in `backend/.env`. Keep provider credentials exclusively on the
backend; never put them in `VITE_` variables. This project is intended for local
use with Groq Free-tier access.

Start the backend:

```sh
cd backend
venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a separate terminal, start the frontend:

```sh
cd frontend
npm run dev
```

Open **http://localhost:5173**. Interactive API documentation is available at
**http://localhost:8000/docs**.

The backend starts without an API key so validation and tests remain available.
Analysis requests that pass input validation return HTTP 503 when the key is missing.

## Configuration

| Variable | Default or purpose |
| --- | --- |
| `GROQ_API_KEY` | Required for analysis; backend only |
| `GROQ_MODEL` | `openai/gpt-oss-120b`; explicitly blank values are rejected |
| `PROVIDER_TIMEOUT_SECONDS` | `30`; accepts values from 1 to 120 |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173`; exact origins only |
| `VITE_API_BASE_URL` | Set to `http://localhost:8000` for local development |

Existing process variables take precedence over backend `.env` values. Restart the
backend after configuration changes. Vite embeds `VITE_API_BASE_URL` at build time;
rebuild the frontend after changing it. The frontend normalizes trailing slashes.

## Usage

1. Select one text-based PDF resume.
2. Paste a nonempty job description.
3. Select **Analyze resume** and review the feedback.
4. Use **Clear session** to reset the selected file, description, results, and history.

[Clearly fictional fixtures](docs/fixtures/README.md) are provided for demonstrations.
Submitting valid inputs with a configured key sends extracted resume text and the
job description to Groq, including when fictional fixtures are used.

Errors preserve inputs for manual recovery. Requests are never retried automatically,
and there are no fallback models or fabricated scores. When a rate-limit delay is
shown, wait before retrying manually.

## Input limits

| Input | Limit |
| --- | --- |
| Resume format | Readable, unencrypted PDF; `.pdf` is case-insensitive |
| File size | 5 MiB |
| PDF length | 20 pages |
| Extracted resume text | 50,000 characters |
| Job description | 20,000 characters after trimming |
| Complete request input estimate | 4,500 tokens, including instructions, schemas, and framing allowance |
| Completion allowance | 2,000 tokens, including reasoning and final JSON |

Oversized inputs are rejected rather than truncated. The token check applies in
addition to file, page, and character limits; it estimates request size, not remaining
shared quota. See [token-budget details](docs/free-tier-budget.md).

Scanned, image-only, blank, corrupt, and password-protected PDFs are unsupported.
OCR and DOCX support are not implemented. Handler-level upload checks do not replace
server or proxy request-body limits.

## API

`POST /analyze` accepts multipart fields `file` and `job_description`. A successful
response contains exactly four fields:

```json
{
  "match_score": 70,
  "strengths": ["Python API project experience"],
  "missing_skills": ["SQL"],
  "suggestions": ["Build a small SQL-backed project"]
}
```

This is an illustrative response. `match_score` must be an integer from 0 to 100.
Each feedback array accepts 0–20 nonempty strings of up to 1,000 characters after
trimming. Invalid or truncated provider output is rejected; reasoning traces are
never included in the public response.

| Status | Meaning |
| --- | --- |
| `400` | Invalid or unreadable file |
| `413` | File, page, text, or token-budget limit exceeded |
| `422` | Missing or unsupported input |
| `502` | Provider failure or invalid analysis output |
| `503` | Missing configuration, unavailable service/model, or provider rate limiting |
| `504` | Provider timeout |

Errors contain a sanitized `detail` message. `/health` reports liveness; `/ready`
reports local configuration only, without checking provider credentials or connectivity.

## Tests

Run backend checks from the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 GROQ_API_KEY= backend/venv/bin/python -m unittest discover -s backend/tests -v
backend/venv/bin/python -m pip check
backend/venv/bin/python scripts/check_no_key.py
```

Run frontend checks:

```sh
cd frontend
npm test
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The suite includes **81 backend tests, 56 frontend tests, and 12 desktop/mobile
Chromium checks**. Automated tests use synthetic documents and mocked providers,
without live AI requests. Browser tests exercise the actual local FastAPI endpoint
with a test-only provider; production contains no test-provider fallback.

GitHub Actions runs the automated checks and credential-free container smoke tests.
See [verification and dependency findings](docs/verification.md) for recorded results
and [frontend testing](frontend/README.md) for browser-test setup.

## Data handling and limitations

- Uploaded documents and extracted text are not intentionally persisted. Upload
  parsing may use temporary disk; browser history is held in memory only.
- Clearing the session does not delete data held by Groq. Cancelling a browser
  request does not guarantee that external processing stops.
- Feedback can overstate skills or suggest unsupported metrics. Use only truthful,
  verifiable qualifications; the score has no independently validated accuracy.
- There is no application authentication, organization-wide quota tracker, or
  persistent database. CORS is not authentication; keep the application local.
- Four moderate development-tooling advisories remain through ESLint's
  `minimatch@10.2.6` dependency; see the [advisory review](docs/verification.md#npm-advisory-review).
- Local Docker execution was unavailable during verification; container smoke tests
  passed in hosted CI. Real mobile hardware and screen-reader speech remain unverified.

## Project structure

```text
backend/                 FastAPI app, provider boundary, validation, and tests
frontend/src/            React interface and frontend validation
frontend/e2e/            Playwright browser journeys
docs/                    Setup records, synthetic fixtures, and verification details
scripts/                 Fixture generation and local smoke checks
.github/workflows/       Automated CI checks
```

For optional local container setup, see the [Docker Compose guide](docs/deployment.md).
