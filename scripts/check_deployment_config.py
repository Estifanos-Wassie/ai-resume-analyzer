"""Static deployment checks using Compose's parser; no daemon or credentials needed."""

import json
import os
from pathlib import Path
import shlex
import subprocess

root = Path(__file__).resolve().parents[1]
# Use explicit safe values; do not expand or print a user's credential configuration.
environment = {**os.environ, 'GROQ_API_KEY': '', 'GROQ_MODEL': 'openai/gpt-oss-120b', 'PUBLIC_ORIGIN': 'http://localhost:8080', 'PROVIDER_TIMEOUT_SECONDS': '30'}
result = subprocess.run(
    ['docker', 'compose', '--env-file', 'deploy/.env.example', 'config', '--format', 'json'],
    cwd=root, env=environment, capture_output=True, text=True, check=True,
)
services = json.loads(result.stdout)['services']
assert services['frontend']['ports'][0]['host_ip'] == '127.0.0.1'
assert not services['backend'].get('ports')
assert not services['frontend'].get('environment')
assert set(services['frontend']['build']['args']) == {'VITE_API_BASE_URL'}
assert services['backend']['environment']['ALLOWED_ORIGINS'] == 'http://localhost:8080'
assert services['backend']['environment']['GROQ_MODEL'] == 'openai/gpt-oss-120b'
assert services['frontend']['build']['args']['VITE_API_BASE_URL'] == 'http://localhost:8080/api'
for model in ['openai/gpt-oss-20b', '']:
    override = subprocess.run(
        ['docker', 'compose', '--env-file', 'deploy/.env.example', 'config', '--format', 'json'],
        cwd=root, env={**environment, 'GROQ_MODEL': model}, capture_output=True, text=True, check=True,
    )
    assert json.loads(override.stdout)['services']['backend']['environment']['GROQ_MODEL'] == model
expected = {'requirements.txt', 'main.py', 'config.py', 'input_validation.py', 'operations.py', 'provider.py', 'schemas.py'}
copied = set()
for line in (root / 'backend/Dockerfile').read_text().splitlines():
    if line.startswith('COPY '):
        for source in shlex.split(line)[1:-1]:
            assert source.startswith('backend/') and (root / source).is_file()
            copied.add(Path(source).name)
assert copied == expected
proxy = (root / 'deploy/nginx.conf').read_text()
assert 'client_max_body_size 6m;' in proxy
assert 'proxy_read_timeout 150s;' in proxy
assert 'proxy_next_upstream off;' in proxy
assert 'proxy_pass http://backend:8000/;' in proxy
print('Compose routing/origins, localhost ports, runtime COPY allowlist, proxy body/deadline policy, and credential separation checked statically.')
