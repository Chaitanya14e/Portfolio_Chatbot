import os
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured in the backend environment."
            )
        _client = Groq(api_key=api_key)
    return _client


def generate_completion(
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
) -> str:
    options: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": 4096,
    }
    if response_format is not None:
        options["response_format"] = response_format

    response = get_client().chat.completions.create(**options)
    if not response.choices:
        raise RuntimeError("Groq returned an empty completion.")

    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Groq returned an empty completion.")
    return content.strip()


def generate_response(prompt: str) -> str:
    return generate_completion([{"role": "user", "content": prompt}])


def generate_response_stream(prompt: str) -> Iterator[str]:
    stream = get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_completion_tokens=4096,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        content = chunk.choices[0].delta.content
        if isinstance(content, str) and content:
            yield content
