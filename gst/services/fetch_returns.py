"""Fetch GST returns into snapshots + normalized imported records."""
from __future__ import annotations

import logging
from typing import Any

from gst.db import SupabaseRest
from gst.integrations.gstzen.client import GstzenClient, GstzenError
from gst.services.fy import fy_tax_periods
from gst.services.jobs import set_job_status
from gst.services.normalize import records_from_return_payload

logger = logging.getLogger("gst.fetch")

RETURN_FETCH_MAP: dict[str, dict[str, Any]] = {
    "gstr1": {"kind": "return", "path": "gstr1/returndata/", "pending": False},
    "gstr1a": {"kind": "return", "path": "gstr1a/returndata/", "pending": False},
    "gstr2": {"kind": "return", "path": "gstr2/returndata/", "pending": False},
    "gstr3b": {"kind": "return", "path": "gstr3b/returndata/", "pending": False},
    "gstr2a": {"kind": "purchase", "path": "gstr2/gstr2a/", "pending": False},
    "gstr2b": {"kind": "purchase", "path": "gstr2/gstr2b/", "pending": False},
    "gstr9": {"kind": "return", "path": "gstr9/returndata/", "pending": True},
}


async def run_fetch_returns_job(auth: dict, job: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    job_id = job["id"]
    await set_job_status(auth, job_id, status="running", progress=5, started=True)
    db = SupabaseRest(auth)
    client = GstzenClient()
    input_payload = job.get("input") or {}
    return_types: list[str] = input_payload.get("return_types") or ["gstr1", "gstr3b", "gstr2b"]
    tax_periods: list[str] = input_payload.get("tax_periods") or fy_tax_periods(case["financial_year"])

    conns = await db.select(
        "gst_connections",
        params={"registration_id": f"eq.{case['registration_id']}", "limit": "1"},
    )
    connection = conns[0] if conns else None

    results: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    total = max(len(return_types) * len(tax_periods), 1)
    done = 0

    for rtype in return_types:
        meta = RETURN_FETCH_MAP.get(rtype)
        if not meta:
            unavailable.append({"return_type": rtype, "reason": "unknown_type"})
            continue
        if meta["pending"]:
            unavailable.append(
                {
                    "return_type": rtype,
                    "reason": "pending_verification",
                    "message": "GSTR-9 fetch pending GSTZen verification. Upload manually.",
                }
            )
            continue

        for period in tax_periods:
            done += 1
            body = {"gstin": case["gstin"], "ret_period": period, "fy": case["financial_year"]}
            if connection and connection.get("session_token"):
                body["session"] = connection["session_token"]
            try:
                payload = await client.api_request(meta["path"], body=body)
                await _upsert_snapshot(db, case, rtype, meta["kind"], period, payload, auth["user_id"])
                imported = records_from_return_payload(rtype, period, payload)
                if imported:
                    await db.delete(
                        "gst_imported_records",
                        {"case_id": f"eq.{case['id']}", "source": f"eq.{rtype}", "tax_period": f"eq.{period}"},
                        use_service=True,
                    )
                    rows = [
                        {
                            "case_id": case["id"],
                            "client_id": case["client_id"],
                            "source": rtype,
                            "tax_period": period,
                            "record_type": rec.get("record_type", "invoice"),
                            "invoice_number": rec.get("invoice_number"),
                            "invoice_date": rec.get("invoice_date"),
                            "counterparty_gstin": rec.get("counterparty_gstin"),
                            "taxable_value": rec.get("taxable_value"),
                            "igst": rec.get("igst"),
                            "cgst": rec.get("cgst"),
                            "sgst": rec.get("sgst"),
                            "cess": rec.get("cess"),
                            "total_tax": rec.get("total_tax"),
                            "raw": rec.get("raw") or {},
                            "fingerprint": rec.get("fingerprint"),
                        }
                        for rec in imported
                    ]
                    for i in range(0, len(rows), 200):
                        await db.insert("gst_imported_records", rows[i : i + 200], use_service=True)
                results.append({"return_type": rtype, "tax_period": period, "ok": True, "records": len(imported)})
            except GstzenError as e:
                logger.warning("fetch %s %s failed: %s", rtype, period, e)
                unavailable.append(
                    {
                        "return_type": rtype,
                        "tax_period": period,
                        "reason": "api_error",
                        "message": str(e),
                        "status_code": e.status_code,
                    }
                )
            await set_job_status(auth, job_id, status="running", progress=min(95, 5 + 90 * done / total))

    await db.update("gst_9c_cases", {"id": f"eq.{case['id']}"}, {"status": "collecting_data"}, use_service=True)
    result = {"fetched": results, "unavailable": unavailable, "message": "Upload docs for unavailable returns."}
    await set_job_status(auth, job_id, status="succeeded", progress=100, result=result, finished=True)
    return result


async def _upsert_snapshot(db, case, rtype, kind, period, payload, user_id) -> None:
    fy = case["financial_year"]
    base = {
        "registration_id": case["registration_id"],
        "client_id": case["client_id"],
        "gstin": case["gstin"],
        "financial_year": fy,
        "tax_period": period,
        "payload": payload,
        "synced_by": user_id,
        "status": "synced",
    }
    if kind == "purchase" or rtype in ("gstr2a", "gstr2b"):
        source = rtype
        if source not in ("gstr2a", "gstr2b", "cdn", "imports", "isd", "tds_tcs", "ecommerce"):
            return
        existing = await db.select(
            "gst_purchase_snapshots",
            params={
                "registration_id": f"eq.{case['registration_id']}",
                "source_type": f"eq.{source}",
                "financial_year": f"eq.{fy}",
                "tax_period": f"eq.{period}",
                "limit": "1",
            },
            use_service=True,
        )
        row = {**base, "source_type": source}
        if existing:
            await db.update("gst_purchase_snapshots", {"id": f"eq.{existing[0]['id']}"}, row, use_service=True)
        else:
            await db.insert("gst_purchase_snapshots", row, use_service=True)
        return
    if rtype not in ("gstr1", "gstr1a", "gstr2", "gstr3b"):
        return
    existing = await db.select(
        "gst_return_snapshots",
        params={
            "registration_id": f"eq.{case['registration_id']}",
            "return_type": f"eq.{rtype}",
            "financial_year": f"eq.{fy}",
            "tax_period": f"eq.{period}",
            "limit": "1",
        },
        use_service=True,
    )
    row = {**base, "return_type": rtype}
    if existing:
        await db.update("gst_return_snapshots", {"id": f"eq.{existing[0]['id']}"}, row, use_service=True)
    else:
        await db.insert("gst_return_snapshots", row, use_service=True)
