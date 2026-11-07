# Resume Analyzer frontend

React/Vite frontend for the existing FastAPI analysis contract. Provider credentials
belong exclusively on the backend. There are no production mock results or fallback
scores.

## Setup

From this directory:

```sh
npm ci
```

If `frontend/.env` does not exist, create it from `.env.example`. Otherwise edit the
existing file without replacing its other settings:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

The URL must be an HTTP(S) address without credentials, query strings, or fragments.
A path prefix is allowed. Trailing slashes are removed before appending `/analyze`.
Missing or invalid configuration produces a controlled service-configuration error.

```sh
npm run dev
```

Open `http://localhost:5173` and run the backend as described in the root README.
For deployment, set `VITE_API_BASE_URL` to the HTTPS backend address **before**
`npm run build`, and allow the frontend origin in backend `ALLOWED_ORIGINS`.
[Vite applies these values at build time](https://vite.dev/guide/env-and-mode), not
when an already-built site starts. Restart the development server after changing
environment files; rebuild/redeploy production assets after changing the URL.

Every `VITE_` variable is public in the browser bundle. Never use a `VITE_` variable
for `GROQ_API_KEY`, passwords, or any other secret. No provider key is needed to run
frontend tests.

## User journey

- Choose one `.pdf` file, case-insensitively, with the keyboard/file picker or by
  dropping it. Empty files, multiple-file drops, and files over 5 MiB are rejected.
  The backend remains authoritative for actual PDF readability, encryption, the
  20-page limit, and the 50,000-character extraction limit. OCR is unsupported.
- Enter a nonempty trimmed job description up to 20,000 characters. Counting uses
  Unicode code points and Python-compatible whitespace trimming. Browser multipart
  serialization converts line breaks to CRLF, so each internal line break counts
  as two characters, matching the text received by FastAPI. Inputs are rejected,
  never silently truncated.
- Submit to receive an AI-estimated match and feedback. The score is not a validated
  employer ATS score or hiring prediction. The notice beside submission explains
  that extracted resume text and the description are sent to Groq.
- Duplicate submissions are blocked synchronously while a request is pending.
  Editing an input cancels the current browser request and clears its visible
  result. A cancelled or older response cannot overwrite newer state. Explicit
  cancellation and unmount cleanup also abort requests. Cancellation does not
  guarantee that external processing or billing stops.
- There is no browser request timeout; the backend enforces its configured provider
  deadline (30 seconds by default, configurable up to 120), excluding upload and
  extraction. Users can cancel without racing a shorter frontend timeout.
- Errors preserve inputs for manual retry. The client validates the success shape
  before rendering and uses only local, sanitized error copy for FastAPI strings,
  validation arrays, provider errors, malformed responses, and network failures.
  Raw response bodies and exception messages are never rendered or logged.
- A valid `Retry-After` pauses submission for the indicated delay, bounded to one
  hour, and displays a manual-retry countdown. No billable request is automatically
  retried. Clearing input/session state does not bypass an active cooldown.
- History contains filenames and estimated scores in React memory only. Reloading
  clears it. Clear session resets the file input, description, result, history,
  errors, and pending request. It does not delete anything held by Groq. No browser
  storage or database is used.

Labels, associated field errors, live loading/error announcements, focus indicators,
keyboard file selection, and focus on completed feedback support keyboard and
assistive-technology use. Layouts retain the existing card and score styling and
adapt to narrow screens and reduced-motion preferences.

## Unit and component tests

```sh
npm test
npm run lint
npm run build
```

Vitest, jsdom, and Testing Library cover input/configuration validation, Unicode
counts, response contracts, safe error normalization, duplicate submissions, late
responses, cancellation/unmount, manual retry/cooldown, and complete session reset.
Fetch is stubbed; an unstubbed request fails rather than reaching a real provider.
`npm run test:watch` starts interactive unit testing.

## Real-browser tests

First install backend requirements into `../backend/venv` as documented in the root
README. Then:

```sh
npx playwright install chromium
npm run test:e2e
```

The suite owns ports 5174 and 8001; stop other services on those ports first. It
builds the real frontend with a test API address, serves the build with Vite preview,
then starts `backend/tests/e2e_server.py`. It never reuses existing servers. Both
processes stop after the run. The generated site lives in ignored
`node_modules/.cache/e2e-site`.

The Python test entry point disables dotenv/key loading, blocks SDK construction
and outbound connections, and injects a synthetic provider through FastAPI's
existing dependency override. Synthetic PDFs are generated with PyMuPDF. Production
`main:app` never imports this harness and has no test mode or fallback provider.
Some additional cases intercept browser responses to verify malformed-success and
network-error handling; the actual-backend journeys do not intercept `/analyze`.

The five journeys run on desktop Chromium (1280×1000) and mobile-emulated Chromium
(390×844), for ten browser checks:

1. Keyboard upload, actual multipart extraction, temporary provider error, manual
   retry, feedback/history, and session clearing. A controlled browser clock
   advances Retry-After without depending on wall-clock scheduling; request counts
   confirm that expiry never sends an automatic retry.
2. Single/multiple drops, missing/whitespace fields, actual blank/corrupt PDFs, and
   successful recovery. Rejected inputs never invoke the test provider.
3. Unicode and CRLF behavior at the actual 20,000-character backend boundary.
4. FastAPI validation arrays, invalid success shapes, non-JSON responses, network
   failure, and manual retry without sensitive-marker disclosure.
5. Duplicate prevention, cancellation on edits, and protection from stale responses.

Screenshots are generated with synthetic content in ignored
`test-results/screenshots/{desktop,mobile}-{feedback,provider-error,validation,cleared}.png`.
Tests check for horizontal overflow. Traces are retained only on failure in
`test-results/`. Use `PLAYWRIGHT_BROWSERS_PATH` consistently for install and test if
placing downloaded browsers outside the default cache.

Verification uses stubs only: live Groq quality, credentials, quotas, model access,
external retention, deployed networking, other browser engines, real mobile
hardware, and screen-reader behavior remain unverified. npm audit currently reports
four moderate findings in the ESLint development dependency chain; compatible
fixes were applied without forcing an ESLint major-version change.
