"""FastAPI application: upload, list/get documents, and a review UI."""
from __future__ import annotations

import json

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import PKG_DIR, Status, default_profile
from .db import get_engine, init_db, make_session_factory
from .extract import make_extractor
from .logging_utils import setup_logging
from .models import AuditLog, Document
from .pipeline import process_upload
from .review import apply_review

_templates = Jinja2Templates(directory=str(PKG_DIR / "templates"))


def create_app(engine: Engine | None = None, profile: str | None = None) -> FastAPI:
    setup_logging()
    engine = engine or get_engine()
    init_db(engine)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="doc-extraction-pipeline", version="0.1.0")
    app.state.session_factory = session_factory
    app.state.profile = profile or default_profile()

    def get_db() -> Session:
        session = app.state.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_extractor():
        return make_extractor("mock", profile=app.state.profile)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/documents")
    async def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> JSONResponse:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="empty file")
        doc, processed = process_upload(
            db,
            filename=file.filename or "upload.pdf",
            content=content,
            extractor=get_extractor(),
            profile=app.state.profile,
        )
        status_code = 201 if processed else 200
        return JSONResponse(
            status_code=status_code,
            content={
                "id": doc.id,
                "status": doc.status,
                "duplicate": not processed,
                "failed_rules": doc.failed_rules or [],
            },
        )

    @app.get("/documents")
    def list_documents(db: Session = Depends(get_db)) -> list[dict]:
        docs = db.scalars(select(Document).order_by(Document.id)).all()
        return [d.to_dict() for d in docs]

    @app.get("/documents/{doc_id}")
    def get_document(doc_id: int, db: Session = Depends(get_db)) -> dict:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        audit = db.scalars(
            select(AuditLog).where(AuditLog.document_id == doc_id).order_by(AuditLog.id)
        ).all()
        data = doc.to_dict()
        data["audit"] = [a.to_dict() for a in audit]
        return data

    @app.get("/review", response_class=HTMLResponse)
    def review_list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        docs = db.scalars(
            select(Document).where(Document.status == Status.NEEDS_REVIEW).order_by(Document.id)
        ).all()
        return _templates.TemplateResponse(
            request, "review_list.html", {"documents": docs}
        )

    @app.get("/review/{doc_id}", response_class=HTMLResponse)
    def review_detail(request: Request, doc_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        extracted = doc.extracted or {}
        line_items_json = json.dumps(extracted.get("line_items", []), indent=2, ensure_ascii=False)
        return _templates.TemplateResponse(
            request,
            "review_detail.html",
            {
                "doc": doc,
                "extracted": extracted,
                "line_items_json": line_items_json,
                "message": request.query_params.get("message"),
            },
        )

    @app.post("/review/{doc_id}")
    def review_submit(
        doc_id: int,
        db: Session = Depends(get_db),
        supplier_name: str = Form(...),
        invoice_number: str = Form(...),
        invoice_date: str = Form(...),
        currency: str = Form(...),
        net_total: str = Form(...),
        vat_rate: str = Form(...),
        vat_amount: str = Form(...),
        gross_total: str = Form(...),
        line_items: str = Form(...),
        decision: str = Form(...),
    ):
        doc = db.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        try:
            items = json.loads(line_items)
        except json.JSONDecodeError:
            return RedirectResponse(
                url=f"/review/{doc_id}?message=Invalid+line_items+JSON", status_code=303
            )
        edited = {
            "supplier_name": supplier_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "currency": currency,
            "net_total": net_total,
            "vat_rate": vat_rate,
            "vat_amount": vat_amount,
            "gross_total": gross_total,
            "line_items": items,
        }
        try:
            ok, failed = apply_review(db, doc, edited, decision)
        except Exception as exc:
            return RedirectResponse(
                url=f"/review/{doc_id}?message=Rejected:+{exc.__class__.__name__}",
                status_code=303,
            )
        if decision == "approve" and not ok:
            msg = "Still+failing:+" + ",".join(failed)
            return RedirectResponse(url=f"/review/{doc_id}?message={msg}", status_code=303)
        return RedirectResponse(url="/review", status_code=303)

    return app
