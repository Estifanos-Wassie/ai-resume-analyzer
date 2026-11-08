# Reproducibility and verification

## Tested runtimes and clean installation

A `git archive` copy of commit `235199c` was extracted into a new temporary directory
on macOS ARM64. It contained no virtual environment, node_modules, ignored files,
or real `.env`. Dependencies were installed there from the committed Python pins
and npm lockfile. Reviewed new runtime metadata, smoke scripts, and reporting
configuration were subsequently copied there for their own checks; the existing
working environment and real `.env` were not modified.

| Tool | Fresh-install version tested |
| --- | --- |
| Python | 3.14.3 |
| pip | 26.0 |
| Node | 24.21.0 |
| npm | 11.19.0 |
| Chromium | 158.0.8127.18, Playwright build 1254 |

`.python-version` and `.nvmrc` declare Python/Node versions. `packageManager` declares
npm 11.19.0; npm does not automatically install that version. Select the listed
versions with your runtime manager first. If needed, use
`npx --yes npm@11.19.0 ci --prefix frontend` to run the pinned installer without
changing a global npm installation.

Exact installation/check commands from the repository root:

```sh
python3 --version
node --version
npm --version
python3 -m venv backend/venv
backend/venv/bin/python -m pip install pip==26.0
backend/venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
PYTHON_DOTENV_DISABLED=1 GROQ_API_KEY= backend/venv/bin/python -m unittest discover -s backend/tests -v
backend/venv/bin/python -m pip check
backend/venv/bin/python scripts/check_no_key.py
cd frontend
npm test
npm run lint
VITE_API_BASE_URL=http://localhost:8000 npm run build
npx playwright install chromium
npm run test:e2e
```

For a clean source copy that excludes ignored files, `git archive HEAD | tar -x -C
/path/to/an/empty/directory` is equivalent to the copy used here. A normal fresh
Git clone works too. Install browser dependencies on Linux with
`npx playwright install --with-deps chromium`. Use one consistent
`PLAYWRIGHT_BROWSERS_PATH` for install/run if choosing a separate browser cache.

Backend tests use stdlib `unittest`; the pinned runtime requirements already include
httpx/FastAPI/PyMuPDF needed for the harness. There is no missing pytest dependency.
Frontend test dependencies are devDependencies in package.json and fully resolved
in package-lock.json; `npm ci` installs them. Do not omit dev dependencies when
building/testing. Production Nginx ships only the generated static assets.

Observed locally: **58 backend tests, 55 frontend unit/component tests, ten desktop/
mobile Chromium checks, lint, production build, and pip check passed**. The real
backend started without credentials; `/health` returned 200, `/ready` and valid
synthetic `/analyze` returned the documented 503, and test-only routes were absent.
The installed test client emits an existing httpx deprecation warning; tests pass.
No live Groq requests or real resumes were used.

## CI

`.github/workflows/ci.yml` runs on pushes to main, pull requests, and manual dispatch.
It uses Ubuntu 24.04, the declared Python/Node versions, pip 26.0, npm 11.19.0, and
supported v7 actions documented by the official
[checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python),
[setup-node](https://github.com/actions/setup-node), and
[upload-artifact](https://github.com/actions/upload-artifact) repositories.

The `checks` job installs fresh dependencies, runs all tests, lint/build, the no-key
startup check, and Chromium with system dependencies. Playwright has a three-minute
suite timeout and zero retries; each job has a 20-minute timeout. The `containers`
job builds/starts the no-key production images and tests serving, proxy routing,
body limits, health/readiness, Nginx syntax, and absence of application test files.
Both jobs explicitly disable dotenv/key loading and require no repository provider
secret. Repository permissions are `contents: read`; checkout credentials are not
persisted. No workflow commits or pushes are performed.

JUnit reports, Playwright HTML reports, and screenshots are uploaded for seven days
from explicit synthetic-test output directories only. Browser test servers refuse
outbound provider calls. No `.env`, whole working directory, real resumes, or
runtime secrets are uploaded. Locally the workflow passed actionlint. Hosted runs
are separate observations: check the
[repository Actions page](https://github.com/Estifanos-Wassie/ai-resume-analyzer/actions)
for the current result; local passes do not establish a hosted CI pass.

## npm advisory review

The fresh lockfile audit reports four moderate entries from one underlying issue,
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249): pathological
attacker-controlled glob patterns can amplify work and exhaust CPU/memory.
Affected minimatch versions are `>=7.0.0 <11.0.1`; this lockfile has **10.2.6**.

Actual paths:

- `eslint@10.14.0 -> minimatch@10.2.6`
- `eslint@10.14.0 -> @eslint/config-array@0.23.5 -> minimatch@10.2.6` (deduplicated)
- `@eslint/js@10.0.1` is also reported through its ESLint relationship.

Registry inspection confirmed current ESLint 10.14.0 requires `^10.2.6`, current
config-array requires `^10.2.4`, and no patched minimatch 10.x exists. npm proposes
a breaking ESLint downgrade or an incompatible dependency-major substitution,
not a compatible patch. No `npm audit fix --force`, major-version override, or
unrelated major upgrade was used. Previously applied compatible fixes are retained.
Revisit when upstream supports a patched compatible dependency range.

These findings affect lint/configuration tooling, which processes repository files
and glob patterns; they are not shipped in the React/Nginx application. The
separate `npm audit --omit=dev` reported zero known npm advisories at review time.
That is not a claim that the application, Python dependencies, or container images
are vulnerability-free. Do not process untrusted lint glob/config input.

Tracked-source review found no credential-pattern matches or real resume documents.
The existing image asset was inspected as template artwork. Synthetic PDFs are
generated by tests, and real `.env` files remain ignored. This review is not a
complete secret-history audit or an external security assessment.
