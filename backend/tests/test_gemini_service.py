import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import gemini_service
from app.services.fact_extractor import extract_facts


class GeminiServiceTests(unittest.TestCase):
    def test_completion_uses_configured_model_and_returns_content(self):
        response = SimpleNamespace(
            text=" Gemini answer "
        )
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=unittest.mock.Mock(return_value=response)
            )
        )
        with patch.object(gemini_service, "get_client", return_value=client):
            answer = gemini_service.generate_response("Question")

        self.assertEqual(answer, "Gemini answer")
        options = client.models.generate_content.call_args.kwargs
        self.assertEqual(options["model"], gemini_service.GEMINI_MODEL)
        self.assertEqual(options["contents"][0].role, "user")
        self.assertEqual(options["contents"][0].parts[0].text, "Question")
        self.assertEqual(options["config"].temperature, 0.2)

    def test_stream_yields_incremental_text_deltas(self):
        stream = [
            SimpleNamespace(text="First "),
            SimpleNamespace(text="answer"),
        ]
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content_stream=unittest.mock.Mock(return_value=stream)
            )
        )
        with patch.object(gemini_service, "get_client", return_value=client):
            self.assertEqual(
                list(gemini_service.generate_response_stream("Question")),
                ["First ", "answer"],
            )
        self.assertEqual(
            client.models.generate_content_stream.call_args.kwargs["model"],
            gemini_service.GEMINI_MODEL,
        )

    def test_missing_api_key_fails_explicitly(self):
        with (
            patch.object(gemini_service, "_client", None),
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"),
        ):
            gemini_service.get_client()

    def test_request_maps_system_instruction_and_json_mode(self):
        contents, config = gemini_service._build_request(
            [
                {"role": "system", "content": "Follow the schema."},
                {"role": "user", "content": "Extract facts."},
            ],
            response_format={"type": "json_object"},
        )

        self.assertEqual(config.system_instruction, "Follow the schema.")
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[0].parts[0].text, "Extract facts.")

    def test_resume_fact_extraction_uses_gemini_json_mode(self):
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
