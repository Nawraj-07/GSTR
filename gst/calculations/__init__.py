from __future__ import annotations

from typing import Any

from gst.calculations.engine import calculate_table_values, validate_draft_values
from gst.calculations.fy_rules import schema_for_fy
from gst.db import SupabaseRest
from gst.services.fy import normalize_fy
from gst.services.jobs import set_job_status


async def run_generate_9c_job(auth: dict, job: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    job_id = job["id"]
    await set_job_status(auth, job_id, status="running", progress=15, started=True)
    db = SupabaseRest(auth)
    fy = normalize_fy(case["financial_year"])
    schema = schema_for_fy(fy)
    schema_key = (job.get("input") or {}).get("fy_schema_key")
    if schema_key:
        schema["fy_schema_key"] = schema_key

    records = await db.select("gst_imported_records", params={"case_id": f"eq.{case['id']}"}, use_service=True)
    by_source: dict[str, list] = {}
    for r in records:
        by_source.setdefault(r.get("source") or "other", []).append(r)
    adjustments = await db.select("gst_9c_adjustments", params={"case_id": f"eq.{case['id']}"}, use_service=True)
    values = calculate_table_values(case=case, records_by_source=by_source, adjustments=adjustments, schema=schema)
    warnings = validate_draft_values(values)
    await set_job_status(auth, job_id, status="running", progress=70)

    existing = await db.select(
        "gst_9c_drafts",
        params={"case_id": f"eq.{case['id']}", "order": "version.desc", "limit": "1"},
        use_service=True,
    )
    version = (existing[0]["version"] + 1) if existing else 1
    if existing:
        await db.update("gst_9c_drafts", {"id": f"eq.{existing[0]['id']}"}, {"status": "superseded"}, use_service=True)

    drafts = await db.insert(
        "gst_9c_drafts",
        {
            "case_id": case["id"],
            "client_id": case["client_id"],
            "version": version,
            "status": "draft",
            "fy_schema_key": schema["fy_schema_key"],
            "summary": {
                "warnings": warnings,
                "disclaimer": schema.get("disclaimer"),
                "record_counts": {k: len(v) for k, v in by_source.items()},
            },
            "created_by": auth["user_id"],
        },
        use_service=True,
    )
    draft = drafts[0]
    value_rows = [{"draft_id": draft["id"], "case_id": case["id"], "client_id": case["client_id"], **v} for v in values]
    for i in range(0, len(value_rows), 200):
        await db.insert("gst_9c_table_values", value_rows[i : i + 200], use_service=True)
    await db.update("gst_9c_cases", {"id": f"eq.{case['id']}"}, {"status": "in_review"}, use_service=True)
    result = {"draft_id": draft["id"], "version": version, "warnings": warnings, "value_count": len(values)}
    await set_job_status(auth, job_id, status="succeeded", progress=100, result=result, finished=True)
    return result
