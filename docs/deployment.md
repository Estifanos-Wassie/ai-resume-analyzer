# Container deployment

This repository supplies one deployment layout: a built React frontend served by
Nginx, with `/api/` reverse-proxied to an unpublished FastAPI service. It creates no
cloud resources and binds the local demo to `127.0.0.1:8080` only. Docker Engine
and the Compose plugin are prerequisites.

## Credential-free local smoke test

From the repository root, after installing the Python dependencies:

```sh
python3 scripts/check_deployment_config.py
GROQ_API_KEY= docker compose --env-file deploy/.env.example config --quiet
GROQ_API_KEY= docker compose --env-file deploy/.env.example up --build --detach --wait --wait-timeout 180
backend/venv/bin/python scripts/smoke_deployment.py
GROQ_API_KEY= docker compose --env-file deploy/.env.example exec -T frontend nginx -t
GROQ_API_KEY= docker compose --env-file deploy/.env.example down --volumes
```

Open `http://localhost:8080` while the services are running. The explicit empty key
prevents an inherited shell credential from activating billable analysis. No real
`.env` is loaded by the production backend (`PYTHON_DOTENV_DISABLED=1`). The example
contains no credential. Do not run the analysis smoke test against a configured
provider: it refuses to proceed unless `/api/ready` reports missing configuration.

The smoke script checks frontend HTML/assets, `/api/health` (200), `/api/ready`
(503), valid synthetic analysis (503 with the documented missing-configuration
message), a full 5-MiB PDF plus 20,000 Unicode characters, the per-file 413, the
proxy's total-body 413, and absence of `/api/__test/state`. No test provider is used
by these containers; provider-disabled errors exercise the real production path.

## Runtime configuration

To prepare a private configuration file without overwriting an existing one:

```sh
test -e deploy/.env.private || cp deploy/.env.example deploy/.env.private
```

Edit that ignored file locally. Set `PUBLIC_ORIGIN` to the exact browser origin
without a trailing slash, and set `GROQ_API_KEY` only when you intend to enable
billable analysis. `PROVIDER_TIMEOUT_SECONDS` accepts 1–120, default 30. Keep
credentials out of command output, build arguments, frontend variables, and Git.
Shell variables take precedence over the explicit Compose environment file.

`GROQ_MODEL` is a runtime backend setting, defaulting to `openai/gpt-oss-120b`.
Add/update it manually in an existing private file if needed; no real `.env` is
overwritten. Unset selects the default, while explicit blank/whitespace fails
central validation. Compose preserves blank values rather than defaulting them.
The [migration guide](model-migration.md) documents the strict-schema/low-reasoning
request profile required for an override. No model API calls are used to validate
configuration, and no failure triggers a model switch. Recreate the backend after
model changes; frontend routing/schema and the Groq provider stay unchanged.

```sh
docker compose --env-file deploy/.env.private up --build --detach --wait --wait-timeout 180
docker compose --env-file deploy/.env.private down
```

Compose builds `VITE_API_BASE_URL=${PUBLIC_ORIGIN}/api` into the frontend and gives
only `${PUBLIC_ORIGIN}` to backend `ALLOWED_ORIGINS`. Changing the public origin
requires rebuilding/recreating the frontend. The backend key is a runtime variable
on the backend service only; it is never a build argument or frontend environment
variable. The API container exposes no host port. Do not mount application source,
`.env` files, or tests into these production containers.

`backend/Dockerfile` copies an explicit allowlist of runtime modules, excluding
`backend/tests/e2e_server.py`, test overrides, and local environments. The build
context is deny-by-default through `.dockerignore`. The frontend final stage
contains only Nginx configuration and built static assets, with no node_modules or
test code. Production `main:app` has no environment switch that activates stubbing.
Images use versioned Python 3.14.3, Node 24.21.0, and Nginx 1.30.6 tags. Tags are not
immutable digests; image/OS package updates and image vulnerability scanning remain
ongoing maintenance.

## Limits, timeouts, and public exposure

Nginx accepts at most **6 MiB total request body** (6,291,456 bytes). That allows a
5-MiB file, up to 80,000 UTF-8 bytes for 20,000 Unicode job-description characters,
and ordinary multipart overhead. This total-body limit is separate from the
backend's **5-MiB per-file limit**, 20-page limit, and text limits. An upload may
pass the proxy and still receive a backend 413. Bodies over 6 MiB are rejected
before FastAPI parses/spools them. An outer gateway must also allow this size.

The proxy uses 5-second connect, 30-second send/body inactivity, and 150-second
upstream read inactivity timeouts. The 150 seconds exceeds the largest permitted
120-second provider deadline, with 30 seconds for extraction/response overhead.
It is not an absolute end-to-end request deadline. Resource-intensive PDF parsing
is not separately timeboxed. Uvicorn allows 135 seconds for graceful request
shutdown, and Compose allows 150 seconds before termination, leaving time for the
provider's bounded cleanup. `proxy_next_upstream off` prevents proxy retries of
analysis requests; backend and frontend also never retry them automatically.

For a public deployment, terminate **HTTPS** at a trusted ingress/load balancer on
the host, forward to `127.0.0.1:8080`, set `PUBLIC_ORIGIN=https://your-host.example`,
and rebuild. Configure that ingress with matching body limits and at least the
proxy's 150-second response timeout. TLS certificates and public ingress are not
provisioned by this Compose file. Keep the API port unpublished and the Compose
host binding on localhost.

Before exposing a billable endpoint, add appropriate authentication/access control,
request/usage limits, concurrency controls, and spending controls. **CORS is not
authentication** and does not stop direct API clients or prevent charges. No public
service or paid resources were created during verification.

## Verification boundary

Locally, the Compose model, origin/routing values, port bindings, Dockerfile COPY
allowlist, and proxy policy were checked statically. Docker CLI 29.8.2 and Compose
5.5.1 are installed, but the daemon was unavailable: its socket at
`/Users/estifanos/.docker/run/docker.sock` did not exist. Local image builds,
`nginx -t`, frontend serving through Nginx, proxy routing/limits, and container
smoke tests therefore remain unexecuted locally. The CI `containers` job executes
these checks on a Docker-enabled runner; consult the actual run before claiming
it passed. Local source startup/browser checks are separate evidence.
