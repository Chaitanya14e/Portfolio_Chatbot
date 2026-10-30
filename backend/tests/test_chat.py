import asyncio
import unittest
from unittest.mock import patch

import fitz
import mongomock
from fastapi import HTTPException, Response

from app.routers import chat
from app.models import PROFILE_FACTS, PROJECTS, PROFILES
from app.schema import ChatRequest
from app.services.resume_parser import extract_pdf_text


class ChatPromptTests(unittest.TestCase):
    resume = "Chaitanya Arora\nSummary: Backend AI Engineering enthusiast"

    def test_personal_introduction_prompt_requires_resume_name(self):
        prompt = chat.build_chat_prompt(
            "Tell me about yourself",
            "verified fact not in resume",
            self.resume,
        )

        self.assertIn("use ONLY information explicitly stated in the", prompt)
        self.assertIn("Do not use other portfolio facts", prompt)
        self.assertIn('The name stated in the resume is "Chaitanya Arora"', prompt)
        self.assertIn('The introduction must begin with: "My name is Chaitanya Arora."', prompt)
        self.assertNotIn("verified fact not in resume", prompt)
        self.assertIn("Do not list", prompt)

    def test_personal_introduction_includes_name_if_model_omits_it(self):
        self.assertEqual(
            chat.ensure_intro_includes_name(
                "I am a backend AI engineering enthusiast.",
                "Tell me about yourself",
                self.resume,
            ),
            "My name is Chaitanya Arora. I am a backend AI engineering enthusiast.",
        )

    def test_personal_introduction_does_not_repeat_the_name(self):
        answer = chat.ensure_intro_includes_name(
            "My name is Chaitanya Arora. I am Chaitanya Arora. I study computer science.",
            "Tell me about yourself",
            self.resume,
        )

        self.assertEqual(
            answer,
            "My name is Chaitanya Arora. I study computer science.",
        )

    def test_prompt_keeps_unknown_facts_unconfirmed_and_uses_project_cards(self):
        prompt = chat.build_chat_prompt(
            "Tell me projects",
            "",
            self.resume,
        )

        self.assertIn("detail is unknown, not proof that it is false", prompt)
        self.assertIn("resume and verified portfolio information do not mention it", prompt)
        self.assertIn("cannot confirm it", prompt)
        self.assertIn("<project-card>", prompt)
        self.assertIn("Frontend projects, Full-stack projects, AI projects, and Other projects", prompt)
        self.assertIn("exact project GitHub URL from the resume or verified facts", prompt)
        self.assertIn("belongs only to that", prompt)
        self.assertIn("briefly redirect to those topics", prompt)

        stale_context_prompt = chat.build_chat_prompt(
            "Tell me about projects",
            "Old project: unrelated project not listed in current resume",
            self.resume,
        )
        self.assertIn("unrelated project", stale_context_prompt)

    def test_verified_projects_are_in_context_and_pending_projects_are_not(self):
        db = mongomock.MongoClient().portfolio_chatbot
        profile_id = str(db[PROFILES].insert_one({"name": "Chaitanya"}).inserted_id)
        db[PROJECTS].insert_many([
            {
                "profile_id": profile_id,
                "name": "Reviewed AI project",
                "description": "Reviewed description",
                "technologies": ["Python"],
                "category": "AI projects",
                "github_url": "https://github.com/example/reviewed",
                "status": "verified",
                "source_type": "github",
            },
            {
                "profile_id": profile_id,
                "name": "Pending project",
                "status": "pending_review",
            },
        ])
        db[PROFILE_FACTS].insert_one({
            "profile_id": profile_id,
            "fact_key": "verified_skill",
            "fact_value": "Python",
            "status": "verified",
        })

        context = chat.build_verified_context(db)
        self.assertIn("Reviewed AI project", context)
        self.assertIn("verified_skill: Python", context)
        self.assertIn("https://github.com/example/reviewed", context)
        self.assertNotIn("Pending project", context)

    def test_chat_endpoints_use_verified_portfolio_context(self):
        context = "Project: Verified repo"
        with (
            patch.object(chat, "get_resume_context", return_value=self.resume),
            patch.object(chat, "build_verified_context", return_value=context),
            patch.object(chat, "generate_response", return_value="Grounded answer"),
        ):
            result = chat.chat(
                ChatRequest(message="Tell me projects"),
                db=None,
            )
        self.assertEqual(result.answer, "Grounded answer")

        with (
            patch.object(chat, "get_resume_context", return_value=self.resume),
            patch.object(chat, "build_verified_context", return_value=context),
            patch.object(chat, "get_client"),
        ):
            response = chat.chat_stream(
                ChatRequest(message="Tell me projects"),
                db=None,
            )
        self.assertIn("text/plain", response.media_type)

    def test_project_card_links_are_limited_to_the_named_resume_project(self):
        resume = "\n".join([
            "Project link for AI-Based Video Anomaly Detection System (GitHub): "
            "https://github.com/example/anomaly",
            "Project link for FunTube (GitHub): https://github.com/example/funtube",
            "Project link for FunTube (View): https://fun-tube-app.vercel.app/",
        ])
        anomaly_card = (
            "<project-card>\n"
            "name: AI-Based Video Anomaly Detection System\n"
            "description: Anomaly detection.\n"
            "github: https://github.com/example/anomaly\n"
            "demo: https://fun-tube-app.vercel.app/\n"
            "</project-card>"
        )
        funtube_card = (
            "<project-card>\n"
            "name: FunTube\n"
            "description: Video sharing.\n"
            "github: https://wrong.example/repo\n"
            "</project-card>"
        )

        sanitized = chat.sanitize_project_cards(
            f"{anomaly_card}\n{funtube_card}",
            resume,
        )

        self.assertIn("github: https://github.com/example/anomaly", sanitized)
        self.assertNotIn("demo: https://fun-tube-app.vercel.app/", sanitized.split(
            "name: FunTube", 1
        )[0])
        self.assertIn("github: https://github.com/example/funtube", sanitized)
        self.assertIn("demo: https://fun-tube-app.vercel.app/", sanitized)
        self.assertNotIn("wrong.example", sanitized)

    def test_streamed_project_card_is_corrected_before_it_is_yielded(self):
        resume = (
            "Project link for FunTube (View): https://fun-tube-app.vercel.app/"
        )
        chunks = iter([
            "Some intro. <project-card>\nname: AI-Based Video Anomaly Detection System\n",
            "demo: https://fun-tube-app.vercel.app/\n</project-card>",
        ])

        output = list(chat.stream_project_cards(chunks, resume))

        self.assertIn("Some intro. ", "".join(output))
        self.assertNotIn("fun-tube-app.vercel.app", "".join(output))
        self.assertTrue(output[-1].endswith("</project-card>"))

    def test_pdf_project_links_are_extracted_with_their_project_names(self):
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 30), "Projects")
        page.insert_text((72, 60), "Demo App")
        page.insert_text((72, 95), "GitHub")
        page.insert_link({
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(72, 83, 110, 100),
            "uri": "https://github.com/example/demo-app",
        })
        page.insert_text((72, 120), "Achievements")
        page.insert_text((72, 150), "Awards")
        page.insert_link({
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(72, 140, 115, 155),
            "uri": "https://example.com/profile",
        })

        text = extract_pdf_text(document.tobytes())

        self.assertIn(
            "Project link for Demo App (GitHub): https://github.com/example/demo-app",
            text,
        )
        self.assertNotIn("https://example.com/profile", text)

    def test_stream_answer_words_paces_words(self):
        delays = []
        chunks = iter(["First ", "sentence. Next ", "sentence"])

        with (
            patch.object(chat, "generate_response_stream", return_value=chunks),
            patch.object(chat.time, "sleep", side_effect=delays.append),
        ):
            words = list(chat.stream_answer_words("prompt"))

        self.assertEqual(words, ["First ", "sentence. ", "Next ", "sentence"])
        self.assertEqual(delays, [0.1, 0.1, 0.1])

    def test_stream_yields_before_model_finishes_generating(self):
        consumed = []

        def generate_chunks(_prompt):
            consumed.append("first")
            yield "First "
            consumed.append("second")
            yield "Second "

        with (
            patch.object(chat, "generate_response_stream", side_effect=generate_chunks),
            patch.object(chat.time, "sleep"),
        ):
            words = chat.stream_answer_words("prompt")
            self.assertEqual(next(words), "First ")
            self.assertEqual(consumed, ["first"])
            self.assertEqual(next(words), "Second ")
            self.assertEqual(consumed, ["first", "second"])

    def test_stream_starts_with_resume_name(self):
        with (
            patch.object(chat, "generate_response_stream", return_value=iter(["I study computer science."])),
            patch.object(chat.time, "sleep"),
        ):
            answer = "".join(chat.stream_answer_words(
                "prompt",
                opening_line="My name is Chaitanya Arora.",
            ))

        self.assertTrue(answer.startswith("My name is Chaitanya Arora."))
        self.assertIn("I study computer science.", answer)

    def test_stream_removes_model_repeating_the_resume_name(self):
        chunks = iter([
            "My name is Chaitanya ",
            "Arora. I study computer science.",
        ])
        with (
            patch.object(chat, "generate_response_stream", return_value=chunks),
            patch.object(chat.time, "sleep"),
        ):
            answer = "".join(chat.stream_answer_words(
                "prompt",
                opening_line="My name is Chaitanya Arora.",
            ))

        self.assertEqual(answer.count("My name is Chaitanya Arora."), 1)
        self.assertIn("I study computer science.", answer)

    def test_stream_endpoint_disables_proxy_buffering(self):
        with (
            patch.object(chat, "get_resume_context", return_value=""),
            patch.object(chat, "get_client"),
        ):
            with patch.object(chat, "build_verified_context", return_value=""):
                response = chat.chat_stream(
                    ChatRequest(message="Tell me about your projects"),
                    db=None,
                )

        self.assertEqual(response.headers["x-accel-buffering"], "no")
        self.assertIn("no-transform", response.headers["cache-control"])
        self.assertTrue(response.media_type.startswith("text/plain"))

    def test_stream_endpoint_reports_missing_gemini_configuration(self):
        with (
            patch.object(chat, "get_resume_context", return_value=""),
            patch.object(chat, "build_verified_context", return_value=""),
            patch.object(
                chat,
                "get_client",
                side_effect=RuntimeError("GEMINI_API_KEY is missing"),
            ),
            self.assertRaises(HTTPException) as error,
        ):
            chat.chat_stream(
                ChatRequest(message="Tell me about your projects"),
                db=None,
            )

        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("GEMINI_API_KEY", error.exception.detail)

    def test_stream_logs_provider_exception_details(self):
        def fail_stream(_prompt):
            raise RuntimeError("Gemini quota exceeded")

        with (
            patch.object(chat, "get_resume_context", return_value=""),
            patch.object(chat, "build_verified_context", return_value=""),
            patch.object(chat, "get_client"),
            patch.object(chat, "generate_response_stream", side_effect=fail_stream),
            patch.object(chat.logger, "exception") as log_exception,
        ):
            response = chat.chat_stream(
                ChatRequest(message="Tell me about your projects"),
                db=None,
            )

            async def collect_body():
                return "".join([chunk async for chunk in response.body_iterator])

            result = asyncio.run(collect_body())

        self.assertIn("chatbot encountered an error", result)
        log_exception.assert_called_once_with("Error while streaming Gemini response")


if __name__ == "__main__":
    unittest.main()