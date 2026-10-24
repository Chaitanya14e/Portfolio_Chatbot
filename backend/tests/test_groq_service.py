import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import groq_service
from app.services.fact_extractor import extract_facts


class GroqServiceTests(unittest.TestCase):
    def test_completion_uses_configured_model_and_returns_content(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=" Groq answer "))]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=unittest.mock.Mock(return_value=response))
            )
        )
        with patch.object(groq_service, "get_client", return_value=client):
            answer = groq_service.generate_response("Question")

        self.assertEqual(answer, "Groq answer")
        options = client.chat.completions.create.call_args.kwargs
        self.assertEqual(options["model"], "openai/gpt-oss-120b")
        self.assertEqual(options["messages"], [{"role": "user", "content": "Question"}])
        self.assertNotIn("stream", options)

    def test_stream_yields_incremental_text_deltas(self):
        stream = [
            SimpleNamespace(choices=[
                SimpleNamespace(delta=SimpleNamespace(content="First "))
            ]),
            SimpleNamespace(choices=[
                SimpleNamespace(delta=SimpleNamespace(content="answer"))
            ]),
        ]
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=unittest.mock.Mock(return_value=stream))
            )
        )
        with patch.object(groq_service, "get_client", return_value=client):
            self.assertEqual(
                list(groq_service.generate_response_stream("Question")),
                ["First ", "answer"],
            )
        self.assertTrue(client.chat.completions.create.call_args.kwargs["stream"])

    def test_missing_api_key_fails_explicitly(self):
        with (
            patch.object(groq_service, "_client", None),
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"),
        ):
            groq_service.get_client()

    def test_resume_fact_extraction_uses_groq_json_mode(self):
        response = json.dumps({"name": "Chaitanya Arora", "projects": []})
        with patch(
            "app.services.fact_extractor.generate_completion",
            return_value=response,
        ) as generate:
            facts = extract_facts("Chaitanya Arora")

        self.assertEqual(facts["name"], "Chaitanya Arora")
        self.assertEqual(facts["status"], "pending_review")
        self.assertEqual(generate.call_args.kwargs["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
