"""Anthropic Messages API extractor (used only by the @live suite)."""
from __future__ import annotations

import httpx

from ..config import DEFAULT_MODEL, anthropic_api_key
from .base import Extractor

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicExtractor(Extractor):
    name = "anthropic"

    def __init__(self, model: str | None = None, timeout: float = 45.0) -> None:
        key = anthropic_api_key()
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; cannot use AnthropicExtractor")
        self._key = key
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout

    def extract(self, text: str, *, attempt: int = 0) -> str:
        from ..prompt import render_prompt

        prompt = render_prompt(text)
        headers = {
            "x-api-key": self._key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(API_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
