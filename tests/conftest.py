from __future__ import annotations

import pytest

from docpipe.db import init_db, make_engine, make_session_factory
from docpipe.invoices import INVOICES_DIR, ensure_invoices, load_ground_truth


@pytest.fixture
def engine(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Session = make_session_factory(engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def invoices():
    ensure_invoices()
    return load_ground_truth()


@pytest.fixture
def sample_invoice(invoices):
    rec = invoices[0]
    content = (INVOICES_DIR / rec["filename"]).read_bytes()
    return content, rec


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient

    from docpipe.api import create_app

    app = create_app(engine=engine, profile="good")
    return TestClient(app)


def valid_invoice_dict() -> dict:
    return {
        "supplier_name": "Acme Ltd",
        "invoice_number": "INV-1",
        "invoice_date": "2025-01-10",
        "currency": "EUR",
        "line_items": [
            {"description": "Widget", "quantity": "2", "unit_price": "10.00", "line_total": "20.00"},
            {"description": "Gadget", "quantity": "1", "unit_price": "30.00", "line_total": "30.00"},
        ],
        "net_total": "50.00",
        "vat_rate": "0.19",
        "vat_amount": "9.50",
        "gross_total": "59.50",
    }
