"""Offline admission tests using synthetic content and real local BPE ranks."""

import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis_request as budget
from config import DEFAULT_GROQ_MODEL
from test_analysis import PRIVATE_TEXT


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')))

    def test_tokenizer_asset_integrity_and_known_ordinary_text_counts(self):
        data = gzip.decompress(budget.TOKENIZER_PATH.read_bytes())
        self.assertEqual(hashlib.sha256(data).hexdigest(), budget.TOKENIZER_SHA256)
        tokenizer = budget.text_tokenizer()
        # GPT-OSS uses the o200k ordinary-text ranks; literal markers stay data.
        self.assertEqual(tokenizer.encode_ordinary('hello world'), [24912, 2375])
        self.assertEqual(tokenizer.decode(tokenizer.encode_ordinary('技能 😀 café e\u0301 <|start|>')), '技能 😀 café e\u0301 <|start|>')

    def test_budget_accounts_for_entire_request_and_padding(self):
        prompt = 'RESUME: Synthetic Candidate 技能😀\nJOB DESCRIPTION: Python'
        parameters = budget.request_parameters(prompt, DEFAULT_GROQ_MODEL)
        expected = len(budget.text_tokenizer().encode_ordinary(json.dumps(parameters, ensure_ascii=False))) + 256
        self.assertEqual(budget.estimated_input_tokens(prompt, DEFAULT_GROQ_MODEL), expected)
        self.assertGreater(expected, len(budget.text_tokenizer().encode_ordinary(prompt)) + 256)
        self.assertEqual(parameters['max_completion_tokens'], 2000)
        self.assertEqual(budget.MAX_INPUT_TOKENS + budget.MAX_COMPLETION_TOKENS + budget.TOKEN_HEADROOM, 8000)
        self.assertEqual(budget.TOKEN_HEADROOM, 1500)

    def test_exact_admission_boundary(self):
        for count in [4499, 4500, 4501]:
            with self.subTest(count=count), patch.object(budget, 'estimated_input_tokens', return_value=count):
                if count > 4500:
                    with self.assertRaises(budget.RequestBudgetExceeded):
                        budget.validate_request_budget('synthetic', DEFAULT_GROQ_MODEL)
                else:
                    self.assertEqual(budget.validate_request_budget('synthetic', DEFAULT_GROQ_MODEL), count)

    def test_unicode_is_tokenized_not_divided_by_four_characters(self):
        ascii_count = budget.estimated_input_tokens('a' * 4000, DEFAULT_GROQ_MODEL)
        unicode_count = budget.estimated_input_tokens('😀' * 4000, DEFAULT_GROQ_MODEL)
        self.assertGreater(unicode_count, ascii_count)
        with self.assertRaises(budget.RequestBudgetExceeded):
            budget.validate_request_budget('😀' * 5000, DEFAULT_GROQ_MODEL)
        for text in ['é', 'e\u0301', '日本語', '<|start|>', '\u0085', '𐍈']:
            with self.subTest(text=text):
                self.assertGreater(budget.estimated_input_tokens(text, DEFAULT_GROQ_MODEL), 256)

    def test_unknown_model_uses_conservative_byte_estimate(self):
        parameters = budget.request_parameters('技能😀', 'synthetic-unknown-model')
        with patch.object(budget, 'text_tokenizer', side_effect=AssertionError('Wrong tokenizer')):
            expected = len(json.dumps(parameters, ensure_ascii=False).encode('utf-8')) + 256
            self.assertEqual(budget.estimated_input_tokens('技能😀', 'synthetic-unknown-model'), expected)

    def test_missing_or_corrupt_asset_fails_closed_without_download(self):
        # Bypass only the memoization to test a fresh process's load path.
        for data in [b'corrupt', gzip.compress(b'wrong hash')]:
            with patch.object(Path, 'read_bytes', return_value=data):
                with self.assertRaises(budget.TokenizerUnavailable):
                    budget.text_tokenizer.__wrapped__()
        with patch.object(Path, 'read_bytes', side_effect=FileNotFoundError(PRIVATE_TEXT)):
            with self.assertRaises(budget.TokenizerUnavailable) as failure:
                budget.text_tokenizer.__wrapped__()
            self.assertNotIn(PRIVATE_TEXT, str(failure.exception))
