"""Extractor abstraction: PDF text in, raw JSON string out (like an LLM)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Extractor(ABC):
    """Anything that turns invoice text into a raw JSON string.

    Returning a raw string (not a parsed object) mirrors a real LLM: the
    pipeline is responsible for parsing, schema-validation and retries.
    """

    name: str = "extractor"

    @abstractmethod
    def extract(self, text: str, *, attempt: int = 0) -> str:
        raise NotImplementedError
