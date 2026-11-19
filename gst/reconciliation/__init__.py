from __future__ import annotations

from typing import Any

from gst.db import SupabaseRest
from gst.reconciliation.engine import compare_sets, compare_totals
from gst.services.jobs import set_job_status


async def run_reconcile_job(auth: dict, job: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    job_id = job["id"]
    await set_job_status(auth, job_id, status="running", progress=10, started=True)
    db = SupabaseRest(auth)
    records = await db.select(
        "gst_imported_records",
        params={"case_id": f"eq.{case['id']}", "select": "*"},
        use_service=True,
    )
    by_source: dict[str, list] = {}
    for r in records:
        by_source.setdefault(r.get("source") or "other", []).append(r)

    comparison_types = (job.get("input") or {}).get("comparison_types") or [
        "gstr1_vs_sales",
        "gstr3b_vs_gstr1",
        "gstr2b_vs_purchases",
        "books_vs_returns",
    ]
    run_summaries = []
    await db.update("gst_9c_cases", {"id": f"eq.{case['id']}"}, {"status": "reconciling"}, use_service=True)

    for ctype in comparison_types:
        if ctype == "gstr1_vs_sales":
            items, summary = compare_sets(
                by_source.get("gstr1", []), by_source.get("sales_register", []), left_label="GSTR-1", right_label="Sales Register"
            )
        elif ctype == "gstr3b_vs_gstr1":
            items, summary = compare_totals(
                by_source.get("gstr3b", []), by_source.get("gstr1", []), left_label="GSTR-3B", right_label="GSTR-1"
            )
        elif ctype == "gstr2b_vs_purchases":
            items, summary = compare_sets(
                by_source.get("gstr2b", []) or by_source.get("gstr2a", []),
                by_source.get("purchase_register", []),
                left_label="GSTR-2B",
                right_label="Purchase Register",
            )
        elif ctype == "gstr9_vs_financials":
            items, summary = compare_totals(
                by_source.get("gstr9", []),
                by_source.get("profit_and_loss", []) or by_source.get("trial_balance", []),
                left_label="GSTR-9",
                right_label="Financial Statements",
            )
        elif ctype == "books_vs_returns":
            books = by_source.get("sales_register", []) + by_source.get("purchase_register", [])
            returns = by_source.get("gstr1", []) + (by_source.get("gstr2b", []) or by_source.get("gstr2a", []))
            items, summary = compare_totals(returns, books, left_label="GST Returns", right_label="Books")
        else:
            continue

        runs = await db.insert(
            "gst_9c_reconciliation_runs",
            {
                "case_id": case["id"],
                "client_id": case["client_id"],
                "comparison_type": ctype,
                "status": "completed",
                "summary": summary,
                "created_by": auth["user_id"],
            },
            use_service=True,
        )
        run = runs[0]
        item_rows = [
            {
                "run_id": run["id"],
                "case_id": case["id"],
                "client_id": case["client_id"],
                "match_status": it["match_status"],
                "difference_type": it.get("difference_type"),
                "difference_amount": it.get("difference_amount"),
                "left_record_id": it.get("left_record_id"),
                "right_record_id": it.get("right_record_id"),
                "explanation": it.get("explanation"),
                "meta": it.get("meta") or {},
            }
            for it in items
        ]
        for i in range(0, len(item_rows), 200):
            await db.insert("gst_9c_reconciliation_items", item_rows[i : i + 200], use_service=True)
        run_summaries.append({"comparison_type": ctype, "run_id": run["id"], "summary": summary})

    await db.update("gst_9c_cases", {"id": f"eq.{case['id']}"}, {"status": "draft_ready"}, use_service=True)
    result = {"runs": run_summaries}
    await set_job_status(auth, job_id, status="succeeded", progress=100, result=result, finished=True)
    return result
