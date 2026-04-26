"""Sentinel agent — extracts a SentinelExtraction from a regulation document."""

from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.lhs.sentinel.prompts import build_system_prompt
from packages.lhs.sentinel.schema import SentinelExtraction


class Sentinel:
    """Reads a regulation document, returns a structured KG-ready extraction.

    The agent is constrained to the 14-type closed vocabulary defined by the
    KG schema. It produces proposals (with temp_ids) that are later materialized
    into the KG after admin approval.
    """

    def __init__(self, llm: OpenAIAdapter) -> None:
        self.llm = llm
        self._system_prompt = build_system_prompt()

    def extract(self, document_text: str, document_label: str) -> SentinelExtraction:
        user_content = (
            f"DOCUMENT LABEL: {document_label}\n"
            f"DOCUMENT TOTAL CHARS: {len(document_text)}\n\n"
            f"=== DOCUMENT BEGIN ===\n"
            f"{document_text}\n"
            f"=== DOCUMENT END ===\n\n"
            "Produce a SentinelExtraction following the schema and the rules in your "
            "system prompt. Be exhaustive on substantive content; mark non-substantive "
            "spans (preamble, signatures, page numbers, contact info) as uncited_spans."
        )
        return self.llm.extract_structured(
            system_prompt=self._system_prompt,
            user_content=user_content,
            response_model=SentinelExtraction,
        )
