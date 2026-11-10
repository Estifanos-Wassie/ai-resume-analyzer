"""Synthetic API and resource-lifecycle regression tests; no network allowed."""

import asyncio
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fitz
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
    import main
import input_validation as inputs
import operations
import provider as providers


VALID_RESULT = {
    "match_score": 75,
    "strengths": ["Python project experience"],
    "missing_skills": ["SQL"],
    "suggestions": ["Describe the synthetic project's outcomes"],
}
PRIVATE_TEXT = "SYNTHETIC_PRIVATE_CONTENT_7391"


def make_pdf(pages=1, text="Synthetic Candidate\nPython FastAPI React", encrypted=False):
    with fitz.open() as document:
        for _ in range(pages):
            page = document.new_page()
            if text:
                page.insert_text((40, 40), text, fontsize=5)
        if encrypted:
            return document.tobytes(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="synthetic-owner",
                user_pw="synthetic-password",
            )
        return document.tobytes()


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {"GROQ_API_KEY": ""}))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")))
        self.enterContext(patch.object(operations.logger, "handlers", [logging.NullHandler()]))
        self.provider = AsyncMock(return_value=json.dumps(VALID_RESULT))
        main.app.dependency_overrides[providers.get_provider] = lambda: self.provider
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = self.enterContext(TestClient(main.app))
        self.pdf = make_pdf()

    def analyze(self, content=None, filename="resume.pdf", jd="Python developer", mime="application/pdf"):
        return self.client.post(
            "/analyze",
            files={"file": (filename, self.pdf if content is None else content, mime)},
            data={"job_description": jd},
        )

    def assert_rejected(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.assertIsInstance(response.json()["detail"], str)
        self.provider.assert_not_awaited()

    def test_valid_extraction_and_analysis(self):
        response = self.analyze(jd="  Python developer  \n")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID_RESULT)
        self.provider.assert_awaited_once()
        prompt = self.provider.call_args.args[0]
        self.assertIn("Synthetic Candidate", prompt)
        self.assertIn("JOB DESCRIPTION:\nPython developer\n", prompt)
        self.assertIn('"additionalProperties": false', prompt)

    def test_uppercase_extension(self):
        self.assertEqual(self.analyze(filename="RESUME.PDF").status_code, 200)

    def test_readable_pdf_does_not_require_trusted_mime(self):
        self.assertEqual(self.analyze(mime="application/octet-stream").status_code, 200)

    def test_non_pdf_extension(self):
        self.assert_rejected(self.analyze(filename="resume.docx"), 400)

    def test_empty_file(self):
        self.assert_rejected(self.analyze(content=b""), 400)

    def test_corrupt_pdf(self):
        self.assert_rejected(self.analyze(content=b"%PDF-1.7\n" + PRIVATE_TEXT.encode()), 400)

    def test_other_format_disguised_as_pdf(self):
        with fitz.open() as document:
            page = document.new_page()
            png = page.get_pixmap().tobytes("png")
        self.assert_rejected(self.analyze(content=png), 400)

    def test_native_parser_failure_is_sanitized_and_document_closed(self):
        original_open = fitz.open
        document = original_open(stream=self.pdf, filetype="pdf")
        with patch.object(inputs.fitz, "open", return_value=document), patch.object(
            fitz.Page, "get_text", side_effect=fitz.mupdf.FzErrorFormat(PRIVATE_TEXT)
        ):
            response = self.analyze()
        self.assert_rejected(response, 400)
        self.assertNotIn(PRIVATE_TEXT, response.text)
        self.assertTrue(document.is_closed)

    def test_password_protected_pdf(self):
        response = self.analyze(content=make_pdf(encrypted=True))
        self.assert_rejected(response, 422)
        self.assertIn("password-protected", response.json()["detail"])

    def test_owner_encrypted_pdf(self):
        with fitz.open(stream=self.pdf, filetype="pdf") as document:
            encrypted = document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="synthetic-owner")
        self.assert_rejected(self.analyze(content=encrypted), 422)

    def test_blank_pdf_requires_text_and_explains_ocr(self):
        response = self.analyze(content=make_pdf(text=""))
        self.assert_rejected(response, 422)
        self.assertIn("text-based PDF", response.json()["detail"])
        self.assertIn("OCR is unsupported", response.json()["detail"])

    def test_image_only_pdf(self):
        with fitz.open() as document:
            page = document.new_page()
            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
            image.clear_with(255)
            page.insert_image(fitz.Rect(40, 40, 100, 100), pixmap=image)
            content = document.tobytes()
        self.assert_rejected(self.analyze(content=content), 422)

    def test_upload_limit(self):
        content = self.pdf + b" " * (inputs.MAX_UPLOAD_BYTES + 1 - len(self.pdf))
        self.assert_rejected(self.analyze(content=content), 413)

    def test_upload_exact_limit_is_accepted(self):
        content = self.pdf + b" " * (inputs.MAX_UPLOAD_BYTES - len(self.pdf))
        self.assertEqual(self.analyze(content=content).status_code, 200)

    def test_page_limit(self):
        self.assert_rejected(self.analyze(content=make_pdf(pages=21)), 413)

    def test_exact_page_limit_is_accepted(self):
        self.assertEqual(self.analyze(content=make_pdf(pages=20)).status_code, 200)

    def test_real_extracted_text_limit(self):
        # 8 pages of synthetic, visible text exceed 50,000 extracted characters.
        content = make_pdf(pages=8, text=("x" * 90 + "\n") * 80)
        self.assert_rejected(self.analyze(content=content), 413)

    def test_extracted_text_limit_boundaries(self):
        for count, expected in [(50_000, 200), (50_001, 413)]:
            with self.subTest(count=count), patch.object(fitz.Page, "get_text", return_value="x" * count):
                self.provider.reset_mock()
                response = self.analyze()
                self.assertEqual(response.status_code, expected)
                if expected != 200:
                    self.provider.assert_not_awaited()

    def test_job_description_limit(self):
        self.assert_rejected(self.analyze(jd="x" * 20_001), 413)

    def test_exact_job_description_limit_is_accepted(self):
        self.assertEqual(self.analyze(jd="x" * 20_000).status_code, 200)

    def test_whitespace_job_description(self):
        self.assert_rejected(self.analyze(jd=" \n\t "), 422)

    def test_missing_and_empty_form_fields(self):
        requests = [
            self.client.post("/analyze", data={"job_description": "Python"}),
            self.client.post("/analyze", files={"file": ("resume.pdf", self.pdf)}),
            self.analyze(jd=""),
            self.client.post("/analyze", data={"file": PRIVATE_TEXT, "job_description": "Python"}),
        ]
        for response in requests:
            with self.subTest(response=response.text):
                self.assert_rejected(response, 422)
                self.assertNotIn(PRIVATE_TEXT, response.text)

    def test_valid_score_boundaries_and_empty_arrays(self):
        for score in [0, 100]:
            with self.subTest(score=score):
                result = {"match_score": score, "strengths": [], "missing_skills": [], "suggestions": []}
                self.provider.return_value = json.dumps(result)
                self.assertEqual(self.analyze().json(), result)

    def test_invalid_score_types_and_values(self):
        for score in [True, False, "75", 75.0, 75.5, -1, 101, None, [], {}, float("nan"), float("inf")]:
            with self.subTest(score=score):
                self.provider.return_value = json.dumps({**VALID_RESULT, "match_score": score})
                self.assertEqual(self.analyze().status_code, 502)

    def test_required_feedback_arrays(self):
        for field in ["strengths", "missing_skills", "suggestions"]:
            with self.subTest(field=field):
                result = dict(VALID_RESULT)
                del result[field]
                self.provider.return_value = json.dumps(result)
                self.assertEqual(self.analyze().status_code, 502)

    def test_missing_score(self):
        result = dict(VALID_RESULT)
        del result["match_score"]
        self.provider.return_value = json.dumps(result)
        self.assertEqual(self.analyze().status_code, 502)

    def test_invalid_feedback_arrays_and_members(self):
        for field in ["strengths", "missing_skills", "suggestions"]:
            for value in [None, "text", {}, [None], [1], [True], [[]], [{}], [""], [" \n\t "], ["x" * 1001], ["x"] * 21]:
                with self.subTest(field=field, value=value):
                    self.provider.return_value = json.dumps({**VALID_RESULT, field: value})
                    self.assertEqual(self.analyze().status_code, 502)

    def test_feedback_boundaries_and_trimming(self):
        self.provider.return_value = json.dumps({**VALID_RESULT, "strengths": ["x" * 1000] * 20, "suggestions": ["  Useful evidence  "]})
        response = self.analyze()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["strengths"]), 20)
        self.assertEqual(response.json()["suggestions"], ["Useful evidence"])

    def test_extra_fields_are_rejected(self):
        self.provider.return_value = json.dumps({**VALID_RESULT, "private_notes": PRIVATE_TEXT})
        self.assertEqual(self.analyze().status_code, 502)

    def test_empty_non_json_and_wrong_shape_output(self):
        for raw in [None, "", "  ", PRIVATE_TEXT, "[]", "null", '"text"', "{}", "```json\n" + json.dumps(VALID_RESULT) + "\n```", json.dumps(VALID_RESULT) + " trailing"]:
            with self.subTest(raw=raw):
                self.provider.return_value = raw
                response = self.analyze()
                self.assertEqual(response.status_code, 502)
                self.assertNotIn(PRIVATE_TEXT, response.text)

    def test_provider_failure_is_sanitized(self):
        self.provider.side_effect = RuntimeError(PRIVATE_TEXT + " synthetic-secret")
        with self.assertLogs(level=logging.DEBUG) as captured:
            response = self.analyze(jd=PRIVATE_TEXT, content=make_pdf(text=PRIVATE_TEXT))
        self.assertEqual(response.status_code, 502)
        for text in [response.text, "\n".join(captured.output)]:
            self.assertNotIn(PRIVATE_TEXT, text)
            self.assertNotIn("synthetic-secret", text)
            self.assertNotIn("Traceback", text)

    def test_invalid_output_is_not_echoed_or_logged(self):
        self.provider.return_value = PRIVATE_TEXT + " synthetic-secret"
        with self.assertLogs(level=logging.DEBUG) as captured:
            response = self.analyze(jd=PRIVATE_TEXT)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(PRIVATE_TEXT, response.text + "\n".join(captured.output))
        self.assertNotIn("synthetic-secret", response.text + "\n".join(captured.output))

    def test_missing_configuration_allows_startup_and_validation(self):
        main.app.dependency_overrides.clear()
        with patch.object(providers, "AsyncGroq") as sdk:
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/health").json(), {"status": "alive"})
            self.assertEqual(self.analyze(content=b"").status_code, 400)
            response = self.analyze()
            self.assertEqual(response.status_code, 503)
            sdk.assert_not_called()

    def test_import_without_key_or_dotenv(self):
        env = {**os.environ, "GROQ_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, "-c", "import main; print('ready')"], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ready")

    def test_openapi_declares_public_response(self):
        schema = self.client.get("/openapi.json").json()
        response = schema["paths"]["/analyze"]["post"]["responses"]["200"]
        self.assertEqual(response["content"]["application/json"]["schema"], {"$ref": "#/components/schemas/AnalysisResult"})
        contract = schema["components"]["schemas"]["AnalysisResult"]
        self.assertEqual(set(contract["required"]), set(VALID_RESULT))
        self.assertFalse(contract["additionalProperties"])

    def test_pdf_document_closed_on_success_and_failure(self):
        original_open = fitz.open
        documents = []

        def track_open(*args, **kwargs):
            document = original_open(*args, **kwargs)
            documents.append(document)
            return document

        with patch.object(inputs.fitz, "open", side_effect=track_open):
            self.assertEqual(self.analyze().status_code, 200)
            self.assertEqual(self.analyze(content=make_pdf(text="")).status_code, 422)
            self.assertEqual(self.analyze(content=make_pdf(encrypted=True)).status_code, 422)
        self.assertTrue(documents)
        self.assertTrue(all(document.is_closed for document in documents))

    def test_upload_closed_after_validation(self):
        for content, jd, name in [(self.pdf, "Python", "resume.pdf"), (b"bad", "Python", "resume.pdf"), (self.pdf, "  ", "resume.pdf"), (self.pdf, "Python", "resume.docx")]:
            with self.subTest(jd=jd, name=name):
                upload = UploadFile(io.BytesIO(content), filename=name)
                try:
                    asyncio.run(inputs.validate_inputs(upload, jd))
                except HTTPException:
                    pass
                self.assertTrue(upload.file.closed)

    def test_upload_read_is_bounded_and_stops_at_limit(self):
        upload = UploadFile(io.BytesIO(b"x" * (inputs.MAX_UPLOAD_BYTES + 100_000)), filename="resume.pdf")
        reads = []
        original_read = upload.read

        async def track_read(size=-1):
            self.assertGreater(size, 0)
            self.assertLessEqual(size, inputs.READ_CHUNK_BYTES)
            data = await original_read(size)
            reads.append(len(data))
            return data

        upload.read = track_read
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(inputs.validate_inputs(upload, "Python"))
        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(sum(reads), inputs.MAX_UPLOAD_BYTES + 1)
        self.assertTrue(upload.file.closed)

    def test_upload_read_failure_is_sanitized_and_closed(self):
        upload = UploadFile(io.BytesIO(self.pdf), filename="resume.pdf")
        upload.read = AsyncMock(side_effect=OSError(PRIVATE_TEXT))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(inputs.validate_inputs(upload, "Python"))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertNotIn(PRIVATE_TEXT, raised.exception.detail)
        self.assertTrue(upload.file.closed)

    def test_sdk_boundary_without_network(self):
        sdk_client = AsyncMock()
        sdk_client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID_RESULT)))])
        async def run():
            provider = providers.GroqProvider(main.Settings())
            try:
                return await provider("synthetic prompt")
            finally:
                await provider.close()

        with patch.dict(os.environ, {"GROQ_API_KEY": "synthetic-test-key"}), patch.object(providers, "AsyncGroq", return_value=sdk_client) as sdk:
            result = asyncio.run(run())
        self.assertEqual(json.loads(result), VALID_RESULT)
        self.assertEqual(sdk.call_args.kwargs["api_key"], "synthetic-test-key")
        self.assertEqual(sdk.call_args.kwargs["timeout"].read, 30.0)
        self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)
        arguments = sdk_client.chat.completions.create.call_args.kwargs
        self.assertEqual(arguments["model"], "openai/gpt-oss-120b")
        self.assertEqual(arguments["messages"][1]["content"], "synthetic prompt")
        sdk_client.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
