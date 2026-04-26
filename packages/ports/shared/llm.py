"""LLMPort — abstract interface for the language model used by Sentinel."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    """Abstract LLM access. Implementations may target any provider."""

    def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: type[T],
    ) -> T:
        """Run a chat completion that returns a structured response.

        The response is guaranteed to validate against `response_model`
        (a Pydantic class). Raises if the model fails to produce valid output.
        """
        ...
