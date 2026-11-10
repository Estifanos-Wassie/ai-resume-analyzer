"""Exercise the real SDK over deterministic in-memory HTTP transport."""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import anyio
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch.dict(os.environ, {"GROQ_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1"}):
    import main
import operations
import provider as providers
from config import DEFAULT_GROQ_MODEL, Settings
from schemas import AnalysisResult
from test_analysis import make_pdf, VALID_RESULT, PRIVATE_TEXT


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.enterContext(patch.dict(os.environ, {"GROQ_API_KEY": "synthetic-test-key"}))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")))
        self.enterContext(patch.object(operations.logger, "handlers", [logging.NullHandler()]))
        self.status = 200
        self.code = "synthetic_error"
        self.headers = {}
        self.raw = json.dumps(VALID_RESULT)
        self.transport_error = None
        self.requests = []
        self.sdk_options = []
        self.http_clients = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.pending = False
        real_sdk = providers.AsyncGroq

        async def handler(request):
            self.requests.append(request)
            self.started.set()
            if self.pending:
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    self.cancelled.set()
                    raise
            if self.transport_error:
                raise self.transport_error(PRIVATE_TEXT, request=request)
            if self.status != 200:
                return httpx.Response(self.status, headers=self.headers, json={"error": {"message": PRIVATE_TEXT, "code": self.code}})
            return httpx.Response(200, json={
                "id": "synthetic-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-oss-120b",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": self.raw, "reasoning": 'SYNTHETIC_PRIVATE_REASONING'}}],
            })

        def factory(**kwargs):
            self.sdk_options.append(kwargs)
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            self.http_clients.append(client)
            return real_sdk(**kwargs, http_client=client, base_url="https://provider.example.test")

        self.enterContext(patch.object(providers, "AsyncGroq", side_effect=factory))
        self.app = main.create_app(Settings())
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test"))
        self.pdf = make_pdf(text=PRIVATE_TEXT)

    async def analyze(self, client=None, jd=PRIVATE_TEXT):
        return await (client or self.client).post("/analyze", files={"file": ("synthetic.pdf", self.pdf)}, data={"job_description": jd}, headers={"X-Request-ID": PRIVATE_TEXT})

    async def test_default_model_and_structured_parameters_reach_sdk_transport(self):
        with self.assertLogs(operations.logger) as captured:
            response = await self.analyze()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID_RESULT)
        payload = json.loads(self.requests[-1].content)
        self.assertEqual(payload['model'], DEFAULT_GROQ_MODEL)
        self.assertEqual(payload['max_completion_tokens'], 8192)
        self.assertNotIn('max_tokens', payload)
        self.assertEqual(payload['reasoning_effort'], 'low')
        self.assertFalse(payload['include_reasoning'])
        self.assertFalse(payload['stream'])
        self.assertNotIn('reasoning_format', payload)
        self.assertEqual(payload['temperature'], 0.3)
        self.assertEqual(payload['response_format'], {
            'type': 'json_schema',
            'json_schema': {'name': 'resume_analysis', 'strict': True, 'schema': AnalysisResult.provider_schema()},
        })
        schema = payload['response_format']['json_schema']['schema']
        self.assertEqual(set(schema['required']), set(VALID_RESULT))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['match_score'], {'type': 'integer'})
        self.assertEqual(schema['properties']['strengths'], {'type': 'array', 'items': {'type': 'string'}})
        self.assertNotIn('SYNTHETIC_PRIVATE_REASONING', response.text + str(captured.output))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.sdk_options[0]['max_retries'], 0)

    async def test_explicit_model_reaches_sdk_without_automatic_switching(self):
        with patch.dict(os.environ, {'GROQ_MODEL': ' openai/gpt-oss-20b '}):
            app = main.create_app(Settings.from_env())
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                self.assertEqual((await self.analyze(client)).status_code, 200)
                self.status = 404
                self.assertEqual((await self.analyze(client)).status_code, 503)
        self.assertEqual([json.loads(request.content)['model'] for request in self.requests], ['openai/gpt-oss-20b'] * 2)

    async def test_structured_mode_still_rejects_bad_provider_content(self):
        for raw in ['', 'not-json', '{"match_score":75}', json.dumps({**VALID_RESULT, 'match_score': True}), json.dumps({**VALID_RESULT, 'strengths': [' ']}), json.dumps({**VALID_RESULT, 'reasoning': 'SYNTHETIC_PRIVATE_REASONING'})]:
            with self.subTest(case=type(raw).__name__):
                self.raw = raw
                response = await self.analyze()
                self.assertEqual(response.status_code, 502)
                self.assertNotIn('SYNTHETIC_PRIVATE_REASONING', response.text)
                self.assertEqual(json.loads(self.requests[-1].content)['response_format']['json_schema']['strict'], True)

    async def test_sdk_status_failure_mapping_and_one_attempt(self):
        for status, expected, category in [
            (401, 503, "authentication"), (403, 503, "authentication"),
            (404, 503, "upstream_not_found"), (408, 504, "timeout"),
            (429, 503, "rate_limited"), (500, 502, "server_failure"),
            (503, 502, "server_failure"), (400, 502, "upstream_rejected"),
            (422, 502, "upstream_rejected"),
        ]:
            with self.subTest(status=status), self.assertLogs(operations.logger) as captured, self.assertLogs(level=logging.DEBUG) as sdk_logs:
                self.status = status
                before = len(self.requests)
                response = await self.analyze()
                self.assertEqual(response.status_code, expected)
                self.assertEqual(len(self.requests) - before, 1)
                event = json.loads(captured.records[-1].getMessage())
                self.assertEqual(event["outcome"], category)
                text = response.text + str(event) + str(sdk_logs.output)
                self.assertNotIn(PRIVATE_TEXT, text)
                self.assertNotIn("synthetic-test-key", text)
                self.assertNotIn("Traceback", text)
                self.assertNotIn("password", response.text.lower())
        self.assertEqual(len(self.sdk_options), 1)

    async def test_unavailable_model_codes(self):
        for status in [400, 404]:
            for code in ["model_not_found", "model_decommissioned", "model_not_available"]:
                with self.subTest(status=status, code=code), self.assertLogs(operations.logger) as captured:
                    self.status, self.code = status, code
                    response = await self.analyze()
                    self.assertEqual(response.status_code, 503)
                    self.assertIn("configured model", response.json()['detail'])
                    self.assertEqual(json.loads(captured.records[-1].getMessage())['outcome'], 'model_unavailable')
        self.assertEqual(len(self.requests), 6)

    async def test_uncoded_404_does_not_claim_a_model_diagnosis(self):
        self.status, self.code = 404, None
        with self.assertLogs(operations.logger) as captured:
            response = await self.analyze()
        self.assertEqual(response.status_code, 503)
        self.assertIn('endpoint or requested resource', response.json()['detail'])
        self.assertNotIn('configured model', response.json()['detail'])
        self.assertEqual(json.loads(captured.records[-1].getMessage())['outcome'], 'upstream_not_found')
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn(PRIVATE_TEXT, response.text + str(captured.output))

    async def test_malformed_404_error_metadata_remains_neutral(self):
        request = httpx.Request('POST', 'https://provider.example.test/openai/v1/chat/completions')
        response = httpx.Response(404, request=request)
        for body in [None, PRIVATE_TEXT, [], {'error': PRIVATE_TEXT}, {'error': {'code': []}}, {'code': 'unknown_code'}]:
            with self.subTest(body_type=type(body).__name__):
                error = providers.APIStatusError(PRIVATE_TEXT, response=response, body=body)
                failure = providers.classify_failure(error)
                self.assertEqual(failure.category, 'upstream_not_found')
                self.assertEqual(failure.status_code, 503)
                self.assertNotIn(PRIVATE_TEXT, failure.detail)

    async def test_connection_and_sdk_timeout_without_retries(self):
        for error, expected in [(httpx.ConnectError, 502), (httpx.ReadTimeout, 504), (httpx.ConnectTimeout, 504), (httpx.PoolTimeout, 504), (httpx.WriteTimeout, 504)]:
            with self.subTest(error=error):
                self.transport_error = error
                before = len(self.requests)
                response = await self.analyze()
                self.assertEqual(response.status_code, expected)
                self.assertEqual(len(self.requests) - before, 1)
                self.assertNotIn(PRIVATE_TEXT, response.text)

    async def test_rate_limit_retry_after_is_safe_and_exposed_to_browser(self):
        self.status = 429
        for value, expected in [("12", "12"), ("999999", "3600"), ("-1", None), (PRIVATE_TEXT, None)]:
            with self.subTest(value=value):
                self.headers = {"Retry-After": value}
                response = await self.client.post("/analyze", files={"file": ("synthetic.pdf", self.pdf)}, data={"job_description": PRIVATE_TEXT}, headers={"Origin": "http://localhost:5173"})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers.get("Retry-After"), expected)
                self.assertIn("temporarily unavailable", response.json()["detail"])
                self.assertIn("Retry-After", response.headers["Access-Control-Expose-Headers"])
                self.assertNotIn(PRIVATE_TEXT, str(response.headers))

    async def test_sdk_timeout_configuration(self):
        app = main.create_app(Settings(provider_timeout_seconds=17))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                self.assertEqual((await self.analyze(client)).status_code, 200)
                options = self.sdk_options[-1]
                self.assertEqual(options["max_retries"], 0)
                self.assertEqual(options["timeout"].as_dict(), {"connect": 5.0, "pool": 5.0, "read": 17, "write": 17})
                self.assertEqual(self.requests[-1].extensions["timeout"], options["timeout"].as_dict())

    async def test_pending_provider_does_not_block_health(self):
        self.pending = True
        task = asyncio.create_task(self.analyze())
        try:
            await asyncio.wait_for(self.started.wait(), timeout=5)
            health = await asyncio.wait_for(self.client.get("/health"), timeout=5)
            self.assertEqual(health.json(), {"status": "alive"})
            self.assertFalse(task.done())
            self.assertEqual(len(self.requests), 1)
        finally:
            self.release.set()
            response = await asyncio.wait_for(task, timeout=5)
        self.assertEqual(response.status_code, 200)

    async def test_total_deadline_cancels_pending_request_without_timing_assertions(self):
        self.pending = True
        scopes = []
        real_fail_after = anyio.fail_after

        @contextmanager
        def capture_deadline(seconds):
            self.assertEqual(seconds, 30.0)
            with real_fail_after(seconds) as scope:
                scopes.append(scope)
                yield scope

        with patch.object(main.anyio, "fail_after", capture_deadline):
            task = asyncio.create_task(self.analyze())
            try:
                await asyncio.wait_for(self.started.wait(), timeout=5)
                scopes[0].deadline = -math.inf  # Expire the real deadline deterministically.
                response = await asyncio.wait_for(task, timeout=5)
            finally:
                self.release.set()
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(response.status_code, 504)
        self.assertTrue(self.cancelled.is_set())
        self.assertEqual(len(self.requests), 1)

    async def test_shared_client_closes_at_shutdown_after_success_and_failure(self):
        for status, error in [(200, None), (429, None), (500, None), (200, httpx.ReadTimeout)]:
            with self.subTest(status=status):
                self.status = status
                self.transport_error = error
                app = main.create_app(Settings())
                before = len(self.sdk_options)
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                        await self.analyze(client)
                        await self.analyze(client)
                        self.assertEqual(len(self.sdk_options) - before, 1)
                        sdk_client = self.http_clients[-1]
                        self.assertFalse(sdk_client.is_closed)
                self.assertTrue(sdk_client.is_closed)
                await app.state.provider.close()  # Idempotent cleanup.

    async def test_shutdown_cleanup_is_shielded_and_bounded(self):
        await self.analyze()
        sdk_client = self.app.state.provider._client
        original_close = sdk_client.close
        started = asyncio.Event()
        scopes = []
        real_move_on_after = anyio.move_on_after

        @contextmanager
        def capture_cleanup(seconds, *, shield):
            self.assertEqual(seconds, 5.0)
            self.assertTrue(shield)
            with real_move_on_after(seconds, shield=shield) as scope:
                scopes.append(scope)
                yield scope

        async def pending_close():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                await original_close()

        with patch.object(sdk_client, "close", pending_close), patch.object(providers.anyio, "move_on_after", capture_cleanup), self.assertLogs(operations.logger) as captured:
            task = asyncio.create_task(self.app.state.provider.close())
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                scopes[0].deadline = -math.inf
                await asyncio.wait_for(task, timeout=5)
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(self.http_clients[-1].is_closed)
        self.assertEqual(json.loads(captured.records[-1].getMessage()), {"event": "provider_cleanup", "outcome": "timeout"})

    async def test_liveness_and_local_readiness_never_construct_client(self):
        for key, status in [("", 503), ("synthetic-unverified-key", 200)]:
            with self.subTest(configured=bool(key)), patch.dict(os.environ, {"GROQ_API_KEY": key}):
                self.assertEqual((await self.client.get("/health")).json(), {"status": "alive"})
                readiness = await self.client.get("/ready")
                self.assertEqual(readiness.status_code, status)
                self.assertEqual(readiness.json(), {"configuration_ready": bool(key), "provider_verified": False, "scope": "local_configuration"})
        self.assertEqual(self.sdk_options, [])
        self.assertEqual(self.requests, [])

    async def test_missing_configuration_is_lazy_and_sanitized(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}), self.assertLogs(operations.logger) as captured:
            response = await self.analyze()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.sdk_options, [])
        self.assertEqual(self.requests, [])
        self.assertNotIn(PRIVATE_TEXT, response.text + str(captured.output))

    async def test_safe_json_operational_logs_and_generated_request_identifier(self):
        for raw, status, outcome in [(json.dumps(VALID_RESULT), 200, "success"), (PRIVATE_TEXT, 502, "invalid_output"), ("", 502, "invalid_output"), (None, 502, "invalid_output"), ('{"match_score":true}', 502, "invalid_output")]:
            with self.subTest(status=status), self.assertLogs(operations.logger) as app_logs, self.assertLogs(level=logging.DEBUG) as sdk_logs:
                self.raw = raw
                response = await self.analyze()
                self.assertEqual(response.status_code, status)
                event = json.loads(app_logs.records[-1].getMessage())
                self.assertEqual(set(event), {"event", "request_id", "duration_ms", "outcome", "status_code"})
                self.assertEqual(event["outcome"], outcome)
                self.assertEqual(event["status_code"], status)
                self.assertEqual(event["request_id"], response.headers["X-Request-ID"])
                self.assertRegex(event["request_id"], r"^[0-9a-f]{32}$")
                self.assertGreaterEqual(event["duration_ms"], 0)
                text = response.text + str(response.headers) + str(app_logs.output) + str(sdk_logs.output)
                self.assertNotIn(PRIVATE_TEXT, text)
                self.assertNotIn("synthetic-test-key", text)
                self.assertNotIn("Traceback", text)
        self.assertIn(PRIVATE_TEXT, self.requests[-1].content.decode())

    async def test_shutdown_cleanup_failure_is_sanitized(self):
        await self.analyze()
        sdk_client = self.app.state.provider._client
        original_close = sdk_client.close

        async def failing_close():
            await original_close()
            raise RuntimeError(PRIVATE_TEXT)

        with patch.object(sdk_client, "close", failing_close), self.assertLogs(operations.logger) as captured:
            await self.app.state.provider.close()
        self.assertTrue(self.http_clients[-1].is_closed)
        self.assertNotIn(PRIVATE_TEXT, str(captured.output))
        self.assertEqual(json.loads(captured.records[-1].getMessage()), {"event": "provider_cleanup", "outcome": "failed"})


class SDKRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def capture_route(self, base_url=None):
        from groq import AsyncGroq
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json={
                'id': 'synthetic', 'object': 'chat.completion', 'created': 0,
                'model': 'openai/gpt-oss-120b',
                'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(VALID_RESULT)}}],
            })

        environment = {'GROQ_API_KEY': 'synthetic-test-key'}
        if base_url is not None:
            environment['GROQ_BASE_URL'] = base_url
        with patch.dict(os.environ, environment, clear=True), patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
                async with AsyncGroq(http_client=transport, max_retries=0) as client:
                    result = await client.chat.completions.create(
                        model='openai/gpt-oss-120b',
                        messages=[{'role': 'user', 'content': 'Synthetic routing check'}],
                    )
                    self.assertEqual(json.loads(result.choices[0].message.content), VALID_RESULT)
        self.assertEqual(len(requests), 1)
        self.assertTrue(transport.is_closed)
        return requests[0]

    async def test_sdk_default_matches_documented_completion_endpoint(self):
        request = await self.capture_route()
        self.assertEqual(str(request.url), 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(request.method, 'POST')
        self.assertEqual(json.loads(request.content)['model'], 'openai/gpt-oss-120b')

    async def test_sdk_root_override_preserves_completion_route(self):
        for base in ['https://api.groq.com', 'https://api.groq.com/']:
            with self.subTest(base=base):
                request = await self.capture_route(base)
                self.assertEqual(str(request.url), 'https://api.groq.com/openai/v1/chat/completions')

    async def test_sdk_appends_full_route_to_base_override_path(self):
        request = await self.capture_route('https://provider.example.test/openai/v1')
        self.assertEqual(request.url.path, '/openai/v1/openai/v1/chat/completions')

    async def test_dotenv_does_not_override_process_configuration(self):
        from dotenv import load_dotenv
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('GROQ_API_KEY=synthetic-file-key\nGROQ_BASE_URL=https://file.example.test\n')
            with patch.dict(os.environ, {'GROQ_API_KEY': 'synthetic-process-key', 'GROQ_BASE_URL': 'https://process.example.test'}, clear=True):
                load_dotenv(path, override=False)
                self.assertEqual(os.environ['GROQ_BASE_URL'], 'https://process.example.test')
                self.assertTrue(os.environ['GROQ_API_KEY'] == 'synthetic-process-key')
            with patch.dict(os.environ, {'GROQ_API_KEY': ''}, clear=True):
                load_dotenv(path, override=False)
                self.assertTrue(os.environ['GROQ_API_KEY'] == '')
                self.assertEqual(os.environ['GROQ_BASE_URL'], 'https://file.example.test')
            with patch.dict(os.environ, {'GROQ_API_KEY': '', 'PYTHON_DOTENV_DISABLED': '1'}, clear=True):
                load_dotenv(path, override=False)
                self.assertNotIn('GROQ_BASE_URL', os.environ)
                self.assertTrue(os.environ['GROQ_API_KEY'] == '')


class ConfigurationTests(unittest.TestCase):
    def test_default_and_explicit_model_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings().groq_model, 'openai/gpt-oss-120b')
            self.assertEqual(Settings.from_env().groq_model, 'openai/gpt-oss-120b')
        with patch.dict(os.environ, {'GROQ_MODEL': ' openai/gpt-oss-20b '}, clear=True):
            self.assertEqual(Settings.from_env().groq_model, 'openai/gpt-oss-20b')

    def test_blank_and_invalid_model_rejected_centrally_without_echo(self):
        for model in ['', '  \n\t', 'invalid model ' + PRIVATE_TEXT, PRIVATE_TEXT * 20]:
            with self.subTest(length=len(model)), patch.dict(os.environ, {'GROQ_MODEL': model}, clear=True):
                with self.assertRaises(ValueError) as raised:
                    Settings.from_env()
                self.assertIn('GROQ_MODEL', str(raised.exception))
                self.assertNotIn(PRIVATE_TEXT, str(raised.exception))
                with self.assertRaises(ValueError):
                    main.create_app()

    def test_blank_model_does_not_fall_back_or_construct_sdk(self):
        with patch.dict(os.environ, {'GROQ_MODEL': ''}), patch.object(providers, 'AsyncGroq') as sdk:
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                main.create_app()
            sdk.assert_not_called()

    def test_environment_settings(self):
        with patch.dict(os.environ, {"PROVIDER_TIMEOUT_SECONDS": "18.5", "ALLOWED_ORIGINS": " https://portfolio.example,https://portfolio.example,http://localhost:5173 "}):
            settings = Settings.from_env()
        self.assertEqual(settings.provider_timeout_seconds, 18.5)
        self.assertEqual(settings.allowed_origins, ("https://portfolio.example", "http://localhost:5173"))

    def test_invalid_timeout_is_rejected_without_echoing_value(self):
        for value in ["0", "121", "nan", "inf", PRIVATE_TEXT]:
            with self.subTest(value=value), patch.dict(os.environ, {"PROVIDER_TIMEOUT_SECONDS": value}):
                with self.assertRaises(ValueError) as raised:
                    Settings.from_env()
                self.assertNotIn(PRIVATE_TEXT, str(raised.exception))

    def test_invalid_origins_fail_closed_without_echoing_value(self):
        for origin in ["*", "https://*.example", "null", "https://example/path", "https://user:password@example", "https://example:bad", PRIVATE_TEXT]:
            with self.subTest(origin=origin), patch.dict(os.environ, {"ALLOWED_ORIGINS": origin}):
                with self.assertRaises(ValueError) as raised:
                    Settings.from_env()
                self.assertNotIn(origin, str(raised.exception))

    def test_retry_after_dates_and_unsafe_values(self):
        fixed = datetime(2026, 11, 7, tzinfo=timezone.utc)
        with patch.object(providers, "datetime") as clock:
            clock.now.return_value = fixed
            self.assertEqual(providers.safe_retry_after(format_datetime(fixed + timedelta(seconds=45))), "45")
            self.assertEqual(providers.safe_retry_after(format_datetime(fixed - timedelta(seconds=45))), "0")
        for value in [None, "", "1.5", "-1", "１２", "x" * 129, PRIVATE_TEXT + "\r\nInjected: value"]:
            self.assertIsNone(providers.safe_retry_after(value))

    def test_cors_development_defaults_and_deployment_allowlist(self):
        from fastapi.testclient import TestClient
        for settings, allowed, denied in [
            (Settings(), ["http://localhost:3000", "http://localhost:5173"], ["https://portfolio.example"]),
            (Settings(allowed_origins=("https://portfolio.example",)), ["https://portfolio.example"], ["http://localhost:5173", "https://evil.example"]),
            (Settings(allowed_origins=()), [], ["http://localhost:5173"]),
        ]:
            with self.subTest(settings=settings), TestClient(main.create_app(settings)) as client:
                for origin in allowed + denied:
                    response = client.options("/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
                    self.assertEqual(response.status_code, 200 if origin in allowed else 400)
                    self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin if origin in allowed else None)
                    self.assertNotEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main()
