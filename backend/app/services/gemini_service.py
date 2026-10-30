import os
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured in the backend environment."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _build_request(
    messages: list[dict[str, str]],
    response_format: dict[str, Any] | None = None,
) -> tuple[list[types.Content], types.GenerateContentConfig]:
    system_instructions = []
    contents = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            system_instructions.append(content)
        elif role in {"user", "assistant"}:
            contents.append(
                types.Content(
                    role="user" if role == "user" else "model",
                    parts=[types.Part.from_text(text=content)],
                )
            )
        else:
            raise ValueError(f"Unsupported Gemini message role: {role}")

    config_options: dict[str, Any] = {
        "temperature": 0.2,
        "max_output_tokens": 4096,
    }
    if system_instructions:
        config_options["system_instruction"] = "\n\n".join(system_instructions)
    if response_format is not None:
        if response_format != {"type": "json_object"}:
            raise ValueError("Gemini only supports JSON object response format.")
        config_options["response_mime_type"] = "application/json"

    return contents, types.GenerateContentConfig(**config_options)


def generate_completion(
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
) -> str:
    contents, config = _build_request(messages, response_format)
    response = get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )
    content = response.text
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Gemini returned an empty completion.")
    return content.strip()


def generate_response(prompt: str) -> str:
    return generate_completion([{"role": "user", "content": prompt}])


def generate_response_stream(prompt: str) -> Iterator[str]:
    contents, config = _build_request([{"role": "user", "content": prompt}])
    stream = get_client().models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )

    for chunk in stream:
        content = chunk.text
        if isinstance(content, str) and content:
            yield content
