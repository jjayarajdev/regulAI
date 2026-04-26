"""OpenAI-backed implementation of `LLMPort`.

Uses the SDK's structured outputs (`client.chat.completions.parse`) which
accepts a Pydantic model and guarantees the response conforms to its schema.
"""

from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from packages.config.settings import settings

T = TypeVar("T", bound=BaseModel)


class OpenAIAdapter:
    """Concrete `LLMPort` against OpenAI."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment or .env")
        self.model = model or settings.openai_model
        self._client = OpenAI(api_key=self.api_key)

    def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: type[T],
    ) -> T:
        response = self._client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=response_model,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            refusal = response.choices[0].message.refusal
            raise RuntimeError(
                f"OpenAI returned no parsed content. Refusal: {refusal!r}"
            )
        return parsed
