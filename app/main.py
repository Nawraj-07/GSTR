"""
FinAxis GSTR-9C microservice (standalone repo: d:\\workspace\\GSTR).

Reuses FinAxis Supabase auth, clients, gst_registrations, and employee_has_client_access.
Does not embed into client-portal — call this API from the portal or tools.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Local uvicorn does not load .env by itself (docker-compose does via env_file).
load_dotenv(_ROOT / ".env")

from gst.auth import require_client_access, require_employee_or_admin
from gst.calculations import run_generate_9c_job
from gst.db import SupabaseRest
from gst.ingestion import run_ingest_document_job
from gst.integrations.gstzen.client import GstzenError
from gst.integrations.gstzen.gstin import validate_gstin
from gst.reconciliation import run_reconcile_job
from gst.reports import run_export_job
from gst.schemas import (
    AdjustmentRequest,
    CaseCreateRequest,
    CaseUpdateRequest,
    ExportRequest,
    FetchReturnsRequest,
    GenerateRequest,
    HealthResponse,
    JobResponse,
    ReconcileRequest,
    ValidateGstinRequest,
    ValidateGstinResponse,
)
from gst.services import cases as cases_svc
from gst.services.audit import write_audit
from gst.services.fetch_returns import run_fetch_returns_job
from gst.services.jobs import create_job, get_job, set_job_status

logger = logging.getLogger("gstr9c")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FinAxis GSTR-9C Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_job_safe(coro) -> None:
    try:
        await coro
    except Exception:
        logger.exception("Background GSTR-9C job failed")


@app.get("/")
def root() -> dict:
    """Browser-friendly landing so opening :8789 does not look 'broken'."""
    return {
        "service": "gstr9c",
        "status": "ok",
        "message": "GSTR-9C API is running. This is not the workbench UI.",
        "health": "/health",
        "docs": "/docs",
        "workbench": "http://localhost:5174",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/v1/gst/schema-check")
async def schema_check() -> dict:
    """Unauthenticated readiness probe: confirms gst_9c tables exist in FinAxis Supabase."""
    import os

    import httpx

    supabase_url = (os.getenv("SUPABASE_URL", "") or os.getenv("VITE_SUPABASE_URL", "")).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_key:
        return {"ok": False, "error": "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured"}
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(
            f"{supabase_url}/rest/v1/gst_9c_cases",
            params={"select": "id", "limit": "1"},
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
        )
    if r.status_code == 200:
        return {"ok": True, "table": "gst_9c_cases"}
    return {
        "ok": False,
        "status": r.status_code,
        "error": r.text[:300],
        "fix": "Run supabase/migrations/20261114_gst_9c.sql in Supabase SQL Editor",
    }



@app.get("/api/v1/gst/capabilities")
async def capabilities(authorization: str | None = Header(default=None)) -> dict:
    await require_employee_or_admin(authorization)
    return {
        "service": "gstr9c",
        "version": "0.2.0",
        "confirmed": [
            "gstin_validation",
            "case_crud",
            "fetch_returns",
            "document_ingest",
            "reconciliation",
            "gstr9c_draft",
            "exports",
        ],
        "pending_verification": ["gstr9_api_fetch", "gstr9c_filing_json"],
        "mvp_excludes": ["automatic_filing"],
    }


@app.get("/api/v1/gst/dashboard")
async def dashboard(authorization: str | None = Header(default=None)) -> dict:
    auth = await require_employee_or_admin(authorization)
    return await cases_svc.case_dashboard_stats(auth)


@app.post("/api/v1/gst/validate-gstin", response_model=ValidateGstinResponse)
async def api_validate_gstin(body: ValidateGstinRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    if body.client_id:
        await require_client_access(auth, body.client_id)
    try:
        raw = await validate_gstin(body.gstin)
    except GstzenError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e)) from e
    return ValidateGstinResponse(gstin=body.gstin.strip().upper(), ok=True, raw=raw)


@app.get("/api/v1/gst/cases")
async def list_cases(client_id: str | None = None, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    return {"cases": await cases_svc.list_cases(auth, client_id=client_id)}


@app.post("/api/v1/gst/cases")
async def create_case(body: CaseCreateRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    return {"case": await cases_svc.create_case(auth, body.model_dump())}


@app.get("/api/v1/gst/cases/{case_id}")
async def get_case(case_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    db = SupabaseRest(auth)
    return {
        "case": case,
        "documents": await db.select("gst_9c_documents", params={"case_id": f"eq.{case_id}", "order": "created_at.desc"}),
        "jobs": await db.select("gst_import_jobs", params={"case_id": f"eq.{case_id}", "order": "created_at.desc", "limit": "20"}),
        "reconciliation_runs": await db.select("gst_9c_reconciliation_runs", params={"case_id": f"eq.{case_id}", "order": "created_at.desc"}),
        "drafts": await db.select("gst_9c_drafts", params={"case_id": f"eq.{case_id}", "order": "version.desc"}),
        "exports": await db.select("gst_9c_exports", params={"case_id": f"eq.{case_id}", "order": "created_at.desc"}),
    }


@app.patch("/api/v1/gst/cases/{case_id}")
async def update_case(case_id: str, body: CaseUpdateRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    return {"case": await cases_svc.update_case(auth, case_id, body.model_dump(exclude_unset=True))}


@app.post("/api/v1/gst/cases/{case_id}/validate-gstin")
async def case_validate_gstin(case_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    try:
        raw = await validate_gstin(case["gstin"])
    except GstzenError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e)) from e
    return {"gstin": case["gstin"], "ok": True, "raw": raw}


@app.post("/api/v1/gst/cases/{case_id}/fetch-returns", response_model=JobResponse)
async def fetch_returns(case_id: str, body: FetchReturnsRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    job = await create_job(
        auth,
        client_id=case["client_id"],
        case_id=case_id,
        registration_id=case["registration_id"],
        job_type="fetch_returns",
        input_payload=body.model_dump(),
    )

    async def _work():
        try:
            await run_fetch_returns_job(auth, job, case)
        except Exception as e:
            await set_job_status(auth, job["id"], status="failed", error_message=str(e), result={"trace": traceback.format_exc()[-1500:]}, finished=True)

    asyncio.create_task(_run_job_safe(_work()))
    return JobResponse(job_id=job["id"], status="queued", message="Fetching returns in background")


@app.post("/api/v1/gst/cases/{case_id}/documents", response_model=JobResponse)
async def upload_document(
    case_id: str,
    doc_type: str = Form(...),
    document_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 40 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 40MB)")
    job = await create_job(
        auth,
        client_id=case["client_id"],
        case_id=case_id,
        registration_id=case["registration_id"],
        job_type="ingest_document",
        input_payload={"doc_type": doc_type, "file_name": file.filename, "document_id": document_id},
    )
    filename = file.filename or "upload.xlsx"

    async def _work():
        try:
            await run_ingest_document_job(auth, job, case, filename=filename, content=content, doc_type=doc_type, document_row_id=document_id)
        except Exception as e:
            await set_job_status(auth, job["id"], status="failed", error_message=str(e), result={"trace": traceback.format_exc()[-1500:]}, finished=True)

    asyncio.create_task(_run_job_safe(_work()))
    return JobResponse(job_id=job["id"], status="queued", message="Ingesting document")


@app.post("/api/v1/gst/cases/{case_id}/reconcile", response_model=JobResponse)
async def reconcile(case_id: str, body: ReconcileRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    job = await create_job(
        auth,
        client_id=case["client_id"],
        case_id=case_id,
        registration_id=case["registration_id"],
        job_type="reconcile",
        input_payload=body.model_dump(),
    )

    async def _work():
        try:
            await run_reconcile_job(auth, job, case)
        except Exception as e:
            await set_job_status(auth, job["id"], status="failed", error_message=str(e), result={"trace": traceback.format_exc()[-1500:]}, finished=True)

    asyncio.create_task(_run_job_safe(_work()))
    return JobResponse(job_id=job["id"], status="queued", message="Reconciliation started")


@app.get("/api/v1/gst/cases/{case_id}/reconciliation")
async def get_reconciliation(
    case_id: str,
    match_status: str | None = None,
    comparison_type: str | None = None,
    invoice_number: str | None = None,
    authorization: str | None = Header(default=None),
):
    auth = await require_employee_or_admin(authorization)
    await cases_svc.get_case(auth, case_id)
    db = SupabaseRest(auth)
    run_params = {"case_id": f"eq.{case_id}", "order": "created_at.desc"}
    if comparison_type:
        run_params["comparison_type"] = f"eq.{comparison_type}"
    runs = await db.select("gst_9c_reconciliation_runs", params=run_params)
    item_params = {"case_id": f"eq.{case_id}", "order": "created_at.desc", "limit": "2000"}
    if match_status:
        item_params["match_status"] = f"eq.{match_status}"
    items = await db.select("gst_9c_reconciliation_items", params=item_params)
    if invoice_number:
        needle = invoice_number.strip().lower()
        items = [i for i in items if needle in str((i.get("meta") or {}).get("invoice_number") or "").lower()]
    return {"runs": runs, "items": items}


@app.post("/api/v1/gst/cases/{case_id}/generate", response_model=JobResponse)
async def generate_9c(case_id: str, body: GenerateRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    job = await create_job(
        auth,
        client_id=case["client_id"],
        case_id=case_id,
        registration_id=case["registration_id"],
        job_type="generate_9c",
        input_payload=body.model_dump(),
    )

    async def _work():
        try:
            await run_generate_9c_job(auth, job, case)
        except Exception as e:
            await set_job_status(auth, job["id"], status="failed", error_message=str(e), result={"trace": traceback.format_exc()[-1500:]}, finished=True)

    asyncio.create_task(_run_job_safe(_work()))
    return JobResponse(job_id=job["id"], status="queued", message="Generating GSTR-9C draft")


@app.get("/api/v1/gst/cases/{case_id}/preview")
async def preview_draft(case_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    await cases_svc.get_case(auth, case_id)
    db = SupabaseRest(auth)
    drafts = await db.select("gst_9c_drafts", params={"case_id": f"eq.{case_id}", "order": "version.desc", "limit": "1"})
    if not drafts:
        return {"draft": None, "values": [], "adjustments": []}
    draft = drafts[0]
    values = await db.select("gst_9c_table_values", params={"draft_id": f"eq.{draft['id']}", "order": "table_code.asc,row_key.asc"})
    adjustments = await db.select("gst_9c_adjustments", params={"case_id": f"eq.{case_id}", "order": "created_at.desc"})
    return {"draft": draft, "values": values, "adjustments": adjustments}


@app.post("/api/v1/gst/cases/{case_id}/adjustments")
async def add_adjustment(case_id: str, body: AdjustmentRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    if not body.explanation.strip():
        raise HTTPException(status_code=400, detail="Explanation is required")
    rows = await SupabaseRest(auth).insert(
        "gst_9c_adjustments",
        {
            "case_id": case_id,
            "client_id": case["client_id"],
            "table_code": body.table_code,
            "field_key": body.field_key,
            "amount": float(body.amount),
            "explanation": body.explanation.strip(),
            "created_by": auth["user_id"],
        },
    )
    await write_audit(auth, case_id=case_id, client_id=case["client_id"], action="adjustment_added", entity_type="gst_9c_adjustments", entity_id=rows[0]["id"])
    return {"adjustment": rows[0]}


@app.post("/api/v1/gst/cases/{case_id}/approve")
async def approve_case(case_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    return {"case": await cases_svc.approve_case(auth, case_id)}


@app.post("/api/v1/gst/cases/{case_id}/exports", response_model=JobResponse)
async def create_export(case_id: str, body: ExportRequest, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    case = await cases_svc.get_case(auth, case_id)
    job = await create_job(
        auth,
        client_id=case["client_id"],
        case_id=case_id,
        registration_id=case["registration_id"],
        job_type="export",
        input_payload=body.model_dump(),
    )

    async def _work():
        try:
            await run_export_job(auth, job, case)
        except Exception as e:
            await set_job_status(auth, job["id"], status="failed", error_message=str(e), result={"trace": traceback.format_exc()[-1500:]}, finished=True)

    asyncio.create_task(_run_job_safe(_work()))
    return JobResponse(job_id=job["id"], status="queued", message="Export started")


@app.get("/api/v1/gst/exports/{export_id}/download")
async def download_export(export_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    rows = await SupabaseRest(auth).select("gst_9c_exports", params={"id": f"eq.{export_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="Export not found")
    row = rows[0]
    await require_client_access(auth, row["client_id"])
    path = Path(row.get("storage_path") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file missing on server")
    return FileResponse(path, filename=row.get("file_name") or path.name)


@app.get("/api/v1/gst/jobs/{job_id}")
async def job_status(job_id: str, authorization: str | None = Header(default=None)):
    auth = await require_employee_or_admin(authorization)
    return {"job": await get_job(auth, job_id)}
