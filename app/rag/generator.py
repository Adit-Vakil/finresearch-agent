"""
LLM answer generator.

Abstracts over different LLM providers behind a single generate() call.
The provider is selected based on which API key is configured.

Priority: Anthropic → Google (Gemini) → OpenAI → stub.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate(system: str, user: str) -> str:
    """Generate a response given a system prompt and user message."""
    if settings.ANTHROPIC_API_KEY:
        return _call_anthropic(system, user)
    if settings.GOOGLE_API_KEY:
        return _call_gemini(system, user)
    if settings.OPENAI_API_KEY:
        return _call_openai(system, user)
    return _stub_response()


def active_model_name() -> str:
    if settings.ANTHROPIC_API_KEY:
        return "anthropic/claude-sonnet-4-6"
    if settings.GOOGLE_API_KEY:
        return "google/gemini-2.0-flash"
    if settings.OPENAI_API_KEY:
        return "openai/gpt-4o-mini"
    return "stub"


def _call_anthropic(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _call_gemini(system: str, user: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=1024,
            temperature=0.1,
        ),
    )
    return response.text


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content


def _stub_response() -> str:
    return (
        "No LLM API key is configured. Set ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
        "or OPENAI_API_KEY in your .env file to enable answer generation. "
        "Retrieved context is available in the sources field."
    )
