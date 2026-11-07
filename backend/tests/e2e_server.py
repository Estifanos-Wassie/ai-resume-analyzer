"""Standalone local browser-test server. Never imported by the production app."""

import json
import os
from pathlib import Path
import socket
import sys

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['GROQ_API_KEY'] = ''
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
import httpx
from fastapi import Response
from groq import RateLimitError
import uvicorn

from config import Settings
from main import create_app
import provider


def forbid_network(*args, **kwargs):
    raise AssertionError('Outbound network forbidden in the browser-test server')


socket.socket.connect = forbid_network
provider.AsyncGroq = forbid_network
app = create_app(Settings(allowed_origins=('http://127.0.0.1:5174',)))
state = {'provider_calls': 0, 'retry_failed': False}


async def stub_analysis(prompt):
    state['provider_calls'] += 1
    if 'SYNTHETIC_PORTFOLIO_RESUME' not in prompt:
        raise AssertionError('Expected extracted synthetic PDF text')
    if 'SYNTHETIC_RETRY_ONCE' in prompt and not state['retry_failed']:
        state['retry_failed'] = True
        request = httpx.Request('POST', 'https://provider.example.test')
        raise RateLimitError('Synthetic rate limit', response=httpx.Response(429, request=request, headers={'Retry-After': '1'}), body=None)
    return json.dumps({
        'match_score': 88,
        'strengths': ['Synthetic PDF text extracted successfully'],
        'missing_skills': ['SQL'],
        'suggestions': ['Add measurable outcomes to the synthetic project'],
    })


app.dependency_overrides[provider.get_provider] = lambda: stub_analysis


@app.post('/__test/reset')
def reset():
    state.update(provider_calls=0, retry_failed=False)
    return {'reset': True}


@app.get('/__test/state')
def test_state():
    return {'provider_calls': state['provider_calls']}


@app.get('/__test/pdf')
def synthetic_pdf(kind: str = 'text'):
    with fitz.open() as document:
        page = document.new_page()
        if kind != 'blank':
            page.insert_text((72, 72), 'SYNTHETIC_PORTFOLIO_RESUME\nSynthetic Candidate\nPython FastAPI React')
        return Response(document.tobytes(), media_type='application/pdf')


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8001, access_log=False)
