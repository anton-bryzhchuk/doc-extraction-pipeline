"""Render the versioned extraction prompt."""
from __future__ import annotations

from functools import lru_cache

from jinja2 import Template

from .config import DEFAULT_PROMPT


@lru_cache(maxsize=4)
def _template(path_str: str) -> Template:
    with open(path_str, encoding="utf-8") as fh:
        return Template(fh.read())


def render_prompt(invoice_text: str, prompt_path=DEFAULT_PROMPT) -> str:
    return _template(str(prompt_path)).render(invoice_text=invoice_text)
