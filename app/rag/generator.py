"""
LLM answer generator.

Abstracts over different LLM providers behind a single generate() call.
The provider is selected based on which API key is configured.  The
abstraction makes it straightforward to swap in a different model later.

Priority: Anthropic → OpenAI → stub (no key configured).
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate(system: str, user: str) -> str:
    """
    Generate a response given a system prompt and user message.

    Returns the raw string response from the LLM.
    """
    if settings.ANTHROPIC_API_KEY:
        return _call_anthropic(system, user)
    if settings.OPENAI_API_KEY:
        return _call_openai(system, user)
    return _stub_response()


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
        "No LLM API key is configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
        "in your .env file to enable answer generation. "
        "Retrieved context is available in the sources field."
    )
