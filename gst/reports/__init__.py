"""Excel / PDF export generation (no automatic filing)."""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gst.db import SupabaseRest
from gst.services.jobs import set_job_status


def _exports_dir(case_id: str) -> Path:
    root = Path(os.getenv("GST_FILES_DIR", "./data/gst"))
    d = root / "exports" / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_reconciliation_excel(runs, items) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Run ID", "Comparison", "Status", "Matched", "Partial", "Mismatch", "Missing GST", "Missing Books", "Net Diff"])
    for r in runs:
        s = r.get("summary") or {}
        ws.append([r.get("id"), r.get("comparison_type"), r.get("status"), s.get("matched"), s.get("partially_matched"), s.get("mismatched"), s.get("missing_in_gst"), s.get("missing_in_books"), s.get("net_difference")])
    wi = wb.create_sheet("Items")
    wi.append(["Run ID", "Match Status", "Difference Type", "Difference Amount", "Explanation", "Invoice"])
    for it in items:
        meta = it.get("meta") or {}
        wi.append([it.get("run_id"), it.get("match_status"), it.get("difference_type"), it.get("difference_amount"), it.get("explanation"), meta.get("invoice_number")])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_gstr9c_excel(case, draft, values) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "GSTR-9C Draft"
    ws.append(["GSTIN", case.get("gstin")])
    ws.append(["Financial Year", case.get("financial_year")])
    ws.append(["Draft Version", draft.get("version")])
    ws.append(["Schema", draft.get("fy_schema_key")])
    ws.append([])
    ws.append(["Table", "Row", "Column", "Amount", "Text", "Sources"])
    for v in values:
        ws.append([v.get("table_code"), v.get("row_key"), v.get("col_key"), v.get("value"), v.get("value_text"), str(v.get("source_refs") or [])[:300]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_gstr9c_pdf_bytes(case, draft, values) -> bytes:
    lines = [
        f"GSTR-9C Draft v{draft.get('version')}",
        f"GSTIN: {case.get('gstin')}",
        f"FY: {case.get('financial_year')}",
        f"Schema: {draft.get('fy_schema_key')}",
        "",
    ]
    for v in values[:200]:
        amt = v.get("value")
        txt = v.get("value_text")
        lines.append(f"{v.get('table_code')}.{v.get('row_key')}: {txt if txt is not None else amt}")
    content = "\n".join(lines)
    safe = content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 40 800 Td 14 TL ({safe[:3500]}) Tj ET"
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream\nendobj\n",
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(x) for x in out))
        out.append(obj)
    xref_pos = sum(len(x) for x in out)
    out.append(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n")
    for off in offsets[1:]:
        out.append(f"{off:010d} 00000 n \n")
    out.append(f"trailer<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n")
    return "".join(out).encode("latin-1", errors="replace")


async def run_export_job(auth: dict, job: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    job_id = job["id"]
    await set_job_status(auth, job_id, status="running", progress=10, started=True)
    db = SupabaseRest(auth)
    export_type = (job.get("input") or {}).get("export_type") or "gstr9c_excel"
    draft_id = (job.get("input") or {}).get("draft_id")
    drafts = await db.select(
        "gst_9c_drafts",
        params=({"id": f"eq.{draft_id}", "limit": "1"} if draft_id else {"case_id": f"eq.{case['id']}", "order": "version.desc", "limit": "1"}),
        use_service=True,
    )
    draft = drafts[0] if drafts else None
    out_dir = _exports_dir(case["id"])
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    if export_type == "reconciliation_excel":
        runs = await db.select("gst_9c_reconciliation_runs", params={"case_id": f"eq.{case['id']}", "order": "created_at.desc"}, use_service=True)
        items = await db.select("gst_9c_reconciliation_items", params={"case_id": f"eq.{case['id']}"}, use_service=True)
        data = build_reconciliation_excel(runs, items)
        filename = f"recon-{case['gstin']}-{ts}.xlsx"
    elif export_type == "gstr9c_pdf":
        if not draft:
            raise ValueError("No draft available. Generate GSTR-9C first.")
        values = await db.select("gst_9c_table_values", params={"draft_id": f"eq.{draft['id']}"}, use_service=True)
        data = build_gstr9c_pdf_bytes(case, draft, values)
        filename = f"gstr9c-{case['gstin']}-v{draft['version']}-{ts}.pdf"
    else:
        if not draft:
            raise ValueError("No draft available. Generate GSTR-9C first.")
        values = await db.select("gst_9c_table_values", params={"draft_id": f"eq.{draft['id']}"}, use_service=True)
        data = build_gstr9c_excel(case, draft, values)
        filename = f"gstr9c-{case['gstin']}-v{draft['version']}-{ts}.xlsx"
        export_type = "gstr9c_excel"

    path = out_dir / filename
    path.write_bytes(data)
    rows = await db.insert(
        "gst_9c_exports",
        {
            "case_id": case["id"],
            "client_id": case["client_id"],
            "draft_id": draft["id"] if draft else None,
            "export_type": export_type,
            "storage_path": str(path.resolve()),
            "file_name": filename,
            "status": "ready",
            "created_by": auth["user_id"],
        },
        use_service=True,
    )
    await db.update("gst_9c_cases", {"id": f"eq.{case['id']}"}, {"status": "exported"}, use_service=True)
    result = {"export_id": rows[0]["id"], "file_name": filename, "storage_path": str(path.resolve())}
    await set_job_status(auth, job_id, status="succeeded", progress=100, result=result, finished=True)
    return result
