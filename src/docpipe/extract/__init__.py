"""Extractor factory."""
from __future__ import annotations

from .base import Extractor
from .mock import PROFILES, MockExtractor

__all__ = ["Extractor", "MockExtractor", "PROFILES", "make_extractor"]


def make_extractor(kind: str = "mock", *, profile: str = "good", seed: int = 2026) -> Extractor:
    if kind == "mock":
        return MockExtractor(profile=profile, seed=seed)
    if kind == "anthropic":
        from .anthropic import AnthropicExtractor

        return AnthropicExtractor()
    raise ValueError(f"unknown extractor {kind!r}; choose 'mock' or 'anthropic'")
