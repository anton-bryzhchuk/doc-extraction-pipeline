"""Deterministic rule-based mock extractor with failure profiles.

Profiles (selectable via CLI/env):

* ``good``          -- parses the invoice text correctly.
* ``noisy``         -- occasionally misses or misreads a field so a business
                       rule breaks (routes to needs_review).
* ``hallucinating`` -- occasionally invents a plausible-but-wrong total
                       (net + vat no longer equals gross -> caught).
* ``malformed``     -- occasionally returns invalid JSON (fails after retries).

Every perturbation is a pure function of the invoice text + a seed, so runs are
reproducible. The parser only works because we generate the PDFs ourselves; it
is NOT a real model (see the README limitations).
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal

from .base import Extractor

PROFILES = ("good", "noisy", "hallucinating", "malformed")

_NUM = r"\d+(?:\.\d+)?"
_ITEM_RE = re.compile(rf"^(?P<desc>.+?)\s+(?P<qty>{_NUM})\s+(?P<unit>{_NUM})\s+(?P<total>{_NUM})$")

_FIELD_RES = {
    "supplier_name": re.compile(r"(?:Supplier|Lieferant):\s*(.+)"),
    "invoice_number": re.compile(r"(?:Invoice Number|Rechnungsnummer):\s*(\S+)"),
    "invoice_date": re.compile(r"(?:Invoice Date|Rechnungsdatum):\s*(\S+)"),
    "currency": re.compile(r"(?:Currency|Waehrung):\s*(\S+)"),
    "net_total": re.compile(rf"(?:Net Total|Nettobetrag):\s*({_NUM})"),
    "vat_amount": re.compile(rf"(?:VAT|MwSt)\s*\([^)]*\):\s*({_NUM})"),
    "gross_total": re.compile(rf"(?:Gross Total|Bruttobetrag):\s*({_NUM})"),
}
_VAT_PCT_RE = re.compile(r"(?:VAT|MwSt)\s*\((\d+)%\)")
_ITEMS_HEADER_RE = re.compile(r"(UnitPrice|Einzelpreis)")
_TOTALS_RE = re.compile(r"(Net Total|Nettobetrag)")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MockExtractor(Extractor):
    name = "mock"

    def __init__(self, profile: str = "good", seed: int = 2026) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}; choose from {PROFILES}")
        self.profile = profile
        self.seed = seed

    # -- deterministic helpers ------------------------------------------------
    def _hash(self, text: str) -> int:
        raw = f"{self.seed}|{text}"
        return int(hashlib.sha256(raw.encode("utf-8")).hexdigest(), 16)

    # -- parsing --------------------------------------------------------------
    def parse(self, text: str) -> dict:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        out: dict = {}

        for key, rx in _FIELD_RES.items():
            m = rx.search(text)
            out[key] = m.group(1).strip() if m else None

        pct = _VAT_PCT_RE.search(text)
        out["vat_rate"] = str(Decimal(pct.group(1)) / Decimal(100)) if pct else None

        items = []
        in_region = False
        for ln in lines:
            if _ITEMS_HEADER_RE.search(ln):
                in_region = True
                continue
            if _TOTALS_RE.search(ln):
                in_region = False
                continue
            if not in_region:
                continue
            m = _ITEM_RE.match(ln)
            if m:
                items.append(
                    {
                        "description": m.group("desc").strip(),
                        "quantity": m.group("qty"),
                        "unit_price": m.group("unit"),
                        "line_total": m.group("total"),
                    }
                )
        out["line_items"] = items
        return out

    # -- profile perturbations ------------------------------------------------
    def _apply_profile(self, data: dict, text: str) -> dict:
        if self.profile == "good":
            return data
        h = self._hash(text)

        if self.profile == "noisy" and h % 5 < 2:
            kind = h % 3
            if kind == 0:
                data["invoice_number"] = ""  # breaks "invoice_number not empty"
            elif kind == 1 and data["line_items"]:
                orig = Decimal(data["line_items"][0]["line_total"])
                data["line_items"][0]["line_total"] = str(_money(orig + Decimal("10.00")))
            else:
                data["net_total"] = str(_money(Decimal(data["net_total"]) + Decimal("3.33")))
            return data

        if self.profile == "hallucinating" and h % 2 == 0:
            # Invent a plausible but wrong gross total.
            orig = Decimal(data["gross_total"])
            data["gross_total"] = str(_money(orig * Decimal("1.07")))
            return data

        return data

    # -- main entry -----------------------------------------------------------
    def extract(self, text: str, *, attempt: int = 0) -> str:
        if self.profile == "malformed" and self._hash(text) % 5 < 2:
            # Invalid JSON on every attempt -> fails after retries.
            return '{"supplier_name": "Broken Co", "invoice_number":  <<<not valid json'
        data = self.parse(text)
        data = self._apply_profile(data, text)
        return json.dumps(data, ensure_ascii=False)
