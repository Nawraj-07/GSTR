from __future__ import annotations

from typing import Any

from gst.db import SupabaseRest
from gst.ingestion.parser import parse_bytes
from gst.services.jobs import set_job_status
from gst.services.normalize import records_from_tabular

DOC_TYPE_TO_SOURCE = {
    "sales_register": "sales_register",
    "purchase_register": "purchase_register",
    "trial_balance": "trial_balance",
    "profit_and_loss": "profit_and_loss",
    "balance_sheet": "balance_sheet",
    "gstr9": "gstr9",
    "other": "other",
}


async def run_ingest_document_job(
    auth: dict,
    job: dict[str, Any],
    case: dict[str, Any],
    *,
    filename: str,
    content: bytes,
    doc_type: str,
    document_row_id: str | None = None,
) -> dict[str, Any]:
    job_id = job["id"]
    await set_job_status(auth, job_id, status="running", progress=10, started=True)
    db = SupabaseRest(auth)
    headers, rows = parse_bytes(filename, content)
    source = DOC_TYPE_TO_SOURCE.get(doc_type, "other")
    records = records_from_tabular(source, rows, headers=headers)
    await set_job_status(auth, job_id, status="running", progress=60)

    docs = await db.insert(
        "gst_9c_documents",
        {
            "case_id": case["id"],
            "client_id": case["client_id"],
            "document_id": document_row_id,
            "doc_type": doc_type,
            "file_name": filename,
            "status": "parsed" if records else "uploaded",
            "uploaded_by": auth["user_id"],
        },
        use_service=True,
    )
    doc_id = docs[0]["id"]
    await db.delete(
        "gst_imported_records",
        {"case_id": f"eq.{case['id']}", "source": f"eq.{source}"},
        use_service=True,
    )
    payload_rows = [
        {
            "case_id": case["id"],
            "client_id": case["client_id"],
            "source": source,
            "source_document_id": doc_id,
            "tax_period": None,
            "record_type": r.get("record_type", "invoice"),
            "invoice_number": r.get("invoice_number"),
            "invoice_date": r.get("invoice_date"),
            "counterparty_gstin": r.get("counterparty_gstin"),
            "taxable_value": r.get("taxable_value"),
            "igst": r.get("igst"),
            "cgst": r.get("cgst"),
            "sgst": r.get("sgst"),
            "cess": r.get("cess"),
            "total_tax": r.get("total_tax"),
            "raw": r.get("raw") or {},
            "fingerprint": r.get("fingerprint"),
        }
        for r in records
    ]
    for i in range(0, len(payload_rows), 200):
        await db.insert("gst_imported_records", payload_rows[i : i + 200], use_service=True)

    result = {
        "document_id": doc_id,
        "source": source,
        "rows_parsed": len(rows),
        "records_imported": len(records),
        "headers": headers[:40],
    }
    await set_job_status(auth, job_id, status="succeeded", progress=100, result=result, finished=True)
    return result
