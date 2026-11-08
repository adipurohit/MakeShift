#!/usr/bin/env python3
"""
Model selection / fallback chain in app/server.py (offline: a fake Gemini client, no key, no network).
The Worker's equivalent is covered in worker_e2e_test.py, which runs the real Worker.

    python3 app/tests/model_chain_test.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# chat_json() imports google.genai.types at call time. Stub it so the real chain loop runs without the SDK.
import types as _t  # noqa: E402
_genai, _types = _t.ModuleType("google.genai"), _t.ModuleType("google.genai.types")
_types.GenerateContentConfig = lambda **kw: kw
_types.ThinkingConfig = lambda **kw: kw
_types.Part = _t.SimpleNamespace(from_text=lambda text: text, from_bytes=lambda **kw: kw)
_types.Content = lambda **kw: kw
_genai.types = _types
_google = sys.modules.setdefault("google", _t.ModuleType("google"))
_google.genai = _genai
sys.modules["google.genai"], sys.modules["google.genai.types"] = _genai, _types

import server  # noqa: E402


class FakeError(Exception):
    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code


class FakeClient:
    """models.generate_content answers per model: 'ok', or an HTTP-style error code."""
    def __init__(self, behavior):
        self.behavior, self.calls = behavior, []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.behavior.get(model, "ok")
        if outcome != "ok":
            raise FakeError(outcome)
        return f"answer-from-{model}"


class ModelChainTests(unittest.TestCase):
    def setUp(self):
        self._saved = (server.TEXT_MODEL, server.FALLBACK_MODEL, server.gemini_client)
        server.TEXT_MODEL, server.FALLBACK_MODEL = "alpha", "bravo, models/charlie ,off,alpha"

    def tearDown(self):
        server.TEXT_MODEL, server.FALLBACK_MODEL, server.gemini_client = self._saved

    def run_with(self, behavior, model=None):
        client = FakeClient(behavior)
        server.gemini_client = lambda: client
        try:
            result = server.chat_json("system", "user", "test", {"type": "object"}, 100, model=model)
        except FakeError as e:
            result = e
        return result, client.calls

    def test_chain_order_dedupes_and_normalises(self):
        self.assertEqual(server.model_chain(), ["alpha", "bravo", "charlie"])
        # a requested model (e.g. the vision model) is tried first, then the fallback list as written
        self.assertEqual(server.model_chain("models/zulu"), ["zulu", "bravo", "charlie", "alpha"])

    def test_off_and_empty_mean_no_fallback(self):
        for value in ("off", "OFF", "", "  ", ","):
            server.FALLBACK_MODEL = value
            self.assertEqual(server.model_chain(), ["alpha"], value)

    def test_main_model_answers_when_healthy(self):
        result, calls = self.run_with({})
        self.assertEqual((result, calls), ("answer-from-alpha", ["alpha"]))

    def test_rate_limited_main_hands_over_to_the_next_model(self):
        result, calls = self.run_with({"alpha": 429})
        self.assertEqual((result, calls), ("answer-from-bravo", ["alpha", "bravo"]))

    def test_chain_continues_past_several_failures(self):
        result, calls = self.run_with({"alpha": 429, "bravo": 503})
        self.assertEqual((result, calls), ("answer-from-charlie", ["alpha", "bravo", "charlie"]))

    def test_unknown_model_name_falls_through_instead_of_failing(self):
        result, calls = self.run_with({"alpha": 404})
        self.assertEqual((result, calls), ("answer-from-bravo", ["alpha", "bravo"]))

    def test_all_models_failing_raises_the_last_error(self):
        result, calls = self.run_with({"alpha": 429, "bravo": 429, "charlie": 503})
        self.assertIsInstance(result, FakeError)
        self.assertEqual((result.code, calls), (503, ["alpha", "bravo", "charlie"]))

    def test_other_errors_are_not_retried_on_another_model(self):
        for code in (400, 401, 403, 500):
            result, calls = self.run_with({"alpha": code})
            self.assertIsInstance(result, FakeError)
            self.assertEqual(calls, ["alpha"], f"code {code} must not fall through")


if __name__ == "__main__":
    unittest.main(verbosity=2)
