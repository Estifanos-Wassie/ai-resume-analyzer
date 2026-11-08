"""Start the real backend without credentials and smoke-test synthetic analysis."""

import os
from pathlib import Path
import subprocess
import sys
import time

import fitz
import httpx


def main():
    backend = Path(__file__).resolve().parents[1] / 'backend'
    environment = {**os.environ, 'GROQ_API_KEY': '', 'PYTHON_DOTENV_DISABLED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8002', '--no-access-log'],
        cwd=backend, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url='http://127.0.0.1:8002', timeout=5, trust_env=False) as client:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Credential-free backend startup failed.')
                try:
                    health = client.get('/health')
                    break
                except httpx.ConnectError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Credential-free backend did not become live.')
            assert health.status_code == 200 and health.json() == {'status': 'alive'}
            ready = client.get('/ready')
            assert ready.status_code == 503 and ready.json()['provider_verified'] is False
            with fitz.open() as document:
                document.new_page().insert_text((72, 72), 'Synthetic Candidate Python FastAPI')
                pdf = document.tobytes()
            result = client.post('/analyze', files={'file': ('synthetic.pdf', pdf)}, data={'job_description': 'Synthetic Python role'})
            assert result.status_code == 503
            assert result.json() == {'detail': 'Analysis is unavailable because the provider is not configured.'}
            assert client.get('/__test/state').status_code == 404
            print('Real backend: health 200, local readiness 503, valid synthetic analysis 503; test routes absent.')
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == '__main__':
    main()
