"""Check a localhost deployment with no provider key; never call a configured provider."""

import re
import sys
from urllib.parse import urlsplit

import fitz
import httpx


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'
    url = urlsplit(base)
    if url.hostname not in ('localhost', '127.0.0.1', '::1') or url.path or url.query or url.fragment:
        raise SystemExit('Smoke checks require a localhost origin without a path.')
    with httpx.Client(base_url=base, timeout=15, trust_env=False) as client:
        ready = client.get('/api/ready')
        if ready.status_code != 503 or ready.json().get('configuration_ready') is not False:
            raise SystemExit('Refusing analysis smoke tests: deployment must have no provider key.')
        assert ready.json()['provider_verified'] is False
        assert client.get('/api/health').json() == {'status': 'alive'}
        page = client.get('/')
        assert page.status_code == 200 and '<div id="root">' in page.text
        asset = re.search(r'src="([^"]+\.js)"', page.text)
        assert asset and client.get(asset.group(1)).status_code == 200
        assert client.get('/api/__test/state').status_code == 404
        with fitz.open() as document:
            document.new_page().insert_text((72, 72), 'Synthetic Candidate Python FastAPI')
            pdf = document.tobytes()
        # Exercise a full-size file plus the maximum UTF-8 job-description payload.
        padded = pdf + b' ' * (5 * 1024 * 1024 - len(pdf))
        result = client.post('/api/analyze', files={'file': ('synthetic.pdf', padded)}, data={'job_description': '\U0001f600' * 20_000})
        # The proxy admits the body, but the independent token policy rejects it.
        assert result.status_code == 413 and 'local Free-tier token budget' in result.json()['detail']
        assert 'x-request-id' in result.headers
        # Compressible maximum-length text still exercises missing configuration.
        result = client.post('/api/analyze', files={'file': ('synthetic.pdf', padded)}, data={'job_description': 'x' * 19_999 + '\U0001f600'})
        assert result.status_code == 503
        assert result.json() == {'detail': 'Analysis is unavailable because the provider is not configured.'}
        oversized_file = client.post('/api/analyze', files={'file': ('synthetic.pdf', padded + b' ')}, data={'job_description': 'Synthetic role'})
        assert oversized_file.status_code == 413 and '5 MiB' in oversized_file.json()['detail']
        oversized_body = client.post('/api/analyze', content=b'x' * (6 * 1024 * 1024 + 1), headers={'Content-Type': 'application/octet-stream'})
        assert oversized_body.status_code == 413
        assert 'x-request-id' not in oversized_body.headers  # Rejected at proxy, before handler.
    print('Frontend/assets, proxy health/readiness, no-key analysis, token/file/body limits, and absent test routes passed.')


if __name__ == '__main__':
    main()
