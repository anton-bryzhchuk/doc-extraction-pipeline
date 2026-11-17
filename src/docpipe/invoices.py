"""Deterministic synthetic-invoice generator + ground truth.

All data is invented (no real people or companies). Invoices vary in layout
(English and German labels), currency, and number of line items (3-8). The
generator is seeded so regenerated PDFs always match the committed
``data/ground_truth.json``.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .config import GROUND_TRUTH_PATH, INVOICES_DIR, N_INVOICES

_SUPPLIERS = [
    "Nordwind Supplies GmbH", "Acme Trading Ltd", "Blaustern Logistik AG",
    "Orion Office Co", "Kyiv Components LLC", "Silverline Parts Ltd",
    "Donau Elektronik GmbH", "Maple & Co Supplies", "Helvetia Werkzeuge AG",
    "Pacific Paper Inc", "Lviv Print House", "Greenfield Hardware Ltd",
]
_ITEMS = [
    "Office Chair", "Desk Lamp", "Printer Paper", "Toner Cartridge",
    "USB Cable", "Monitor Stand", "Keyboard", "Notebook Pack",
    "Whiteboard Marker", "Ethernet Switch", "Power Adapter", "Desk Organizer",
    "Standing Desk", "Webcam", "Headset", "Cable Tray",
]
_CURRENCIES = ["EUR", "USD", "UAH", "GBP"]
_VAT_RATES = [Decimal("0.19"), Decimal("0.20"), Decimal("0.07"), Decimal("0.00")]

# Label sets per language. The mock extractor understands both.
_LABELS = {
    "en": {
        "title": "INVOICE",
        "supplier": "Supplier:",
        "number": "Invoice Number:",
        "date": "Invoice Date:",
        "currency": "Currency:",
        "items": "Items:",
        "header": "Description Qty UnitPrice LineTotal",
        "net": "Net Total:",
        "vat": "VAT ({pct}%):",
        "gross": "Gross Total:",
    },
    "de": {
        "title": "RECHNUNG",
        "supplier": "Lieferant:",
        "number": "Rechnungsnummer:",
        "date": "Rechnungsdatum:",
        "currency": "Waehrung:",
        "items": "Positionen:",
        "header": "Beschreibung Menge Einzelpreis Gesamt",
        "net": "Nettobetrag:",
        "vat": "MwSt ({pct}%):",
        "gross": "Bruttobetrag:",
    },
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _build_invoice(idx: int, rng: random.Random) -> dict:
    lang = "en" if idx % 2 == 0 else "de"
    currency = _CURRENCIES[idx % len(_CURRENCIES)]
    vat_rate = _VAT_RATES[idx % len(_VAT_RATES)]
    supplier = rng.choice(_SUPPLIERS)
    n_items = rng.randint(3, 8)

    start = date(2025, 1, 1)
    invoice_date = start + timedelta(days=rng.randint(0, 300))

    descriptions = rng.sample(_ITEMS, n_items)
    line_items = []
    net = Decimal("0.00")
    for desc in descriptions:
        qty = rng.randint(1, 20)
        unit_price = _money(Decimal(rng.randint(150, 25000)) / Decimal(100))
        line_total = _money(Decimal(qty) * unit_price)
        net += line_total
        line_items.append(
            {
                "description": desc,
                "quantity": str(qty),
                "unit_price": str(unit_price),
                "line_total": str(line_total),
            }
        )
    net = _money(net)
    vat_amount = _money(net * vat_rate)
    gross = _money(net + vat_amount)

    return {
        "lang": lang,
        "supplier_name": supplier,
        "invoice_number": f"INV-{2025000 + idx}",
        "invoice_date": invoice_date.isoformat(),
        "currency": currency,
        "line_items": line_items,
        "net_total": str(net),
        "vat_rate": str(vat_rate),
        "vat_amount": str(vat_amount),
        "gross_total": str(gross),
    }


def _render_pdf(inv: dict, path: Path) -> None:
    lang = inv["lang"]
    lbl = _LABELS[lang]
    pct = int((Decimal(inv["vat_rate"]) * 100).to_integral_value())

    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, y, lbl["title"])
    y -= 36

    c.setFont("Helvetica", 11)
    for key in ("supplier", "number", "date", "currency"):
        value = {
            "supplier": inv["supplier_name"],
            "number": inv["invoice_number"],
            "date": inv["invoice_date"],
            "currency": inv["currency"],
        }[key]
        c.drawString(60, y, f"{lbl[key]} {value}")
        y -= 18

    y -= 12
    c.drawString(60, y, lbl["items"])
    y -= 18
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, lbl["header"])
    y -= 16
    c.setFont("Helvetica", 10)
    for item in inv["line_items"]:
        row = f"{item['description']} {item['quantity']} {item['unit_price']} {item['line_total']}"
        c.drawString(60, y, row)
        y -= 15

    y -= 16
    c.setFont("Helvetica", 11)
    c.drawString(60, y, f"{lbl['net']} {inv['net_total']}")
    y -= 18
    c.drawString(60, y, f"{lbl['vat'].format(pct=pct)} {inv['vat_amount']}")
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, f"{lbl['gross']} {inv['gross_total']}")
    c.showPage()
    c.save()


def generate_all(seed: int = 2026, out_dir: Path = INVOICES_DIR,
                 ground_truth_path: Path = GROUND_TRUTH_PATH) -> list[dict]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    ground_truth: list[dict] = []
    for idx in range(N_INVOICES):
        inv = _build_invoice(idx, rng)
        filename = f"invoice_{idx:02d}.pdf"
        _render_pdf(inv, out_dir / filename)
        record = {k: v for k, v in inv.items() if k != "lang"}
        ground_truth.append({"filename": filename, "lang": inv["lang"], "data": record})

    ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
    ground_truth_path.write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ground_truth


def ensure_invoices(seed: int = 2026) -> None:
    """Generate the PDFs if they are missing (ground truth is committed)."""
    if not INVOICES_DIR.exists() or not any(INVOICES_DIR.glob("*.pdf")):
        generate_all(seed=seed)


def load_ground_truth() -> list[dict]:
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
