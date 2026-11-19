from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from gst.auth import require_client_access
from gst.db import SupabaseRest
from gst.integrations.gstzen.client import GstzenError
from gst.integrations.gstzen.gstin import validate_gstin
from gst.services.audit import write_audit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_cases(auth: dict, client_id: str | None = None) -> list[dict[str, Any]]:
    db = SupabaseRest(auth)
    params: dict[str, str] = {"select": "*", "order": "updated_at.desc"}
    if client_id:
        await require_client_access(auth, client_id)
        params["client_id"] = f"eq.{client_id}"
    return await db.select("gst_9c_cases", params=params)


async def get_case(auth: dict, case_id: str) -> dict[str, Any]:
    case = await SupabaseRest(auth).get_one("gst_9c_cases", case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await require_client_access(auth, case["client_id"])
    return case


async def create_case(auth: dict, body: dict[str, Any]) -> dict[str, Any]:
    client_id = body["client_id"]
    registration_id = body["registration_id"]
    financial_year = body["financial_year"].strip()
    await require_client_access(auth, client_id)

    db = SupabaseRest(auth)
    regs = await db.select(
        "gst_registrations",
        params={"id": f"eq.{registration_id}", "client_id": f"eq.{client_id}", "limit": "1"},
    )
    if not regs:
        raise HTTPException(status_code=404, detail="GST registration not found for this client")
    gstin = (regs[0].get("gstin") or "").upper()

    if body.get("validate_gstin", True):
        try:
            await validate_gstin(gstin)
        except GstzenError as e:
            if e.status_code != 503:
                raise HTTPException(status_code=e.status_code or 502, detail=str(e)) from e

    rows = await db.insert(
        "gst_9c_cases",
        {
            "client_id": client_id,
            "registration_id": registration_id,
            "gstin": gstin,
            "financial_year": financial_year,
            "assigned_to": body.get("assigned_to"),
            "notes": body.get("notes"),
            "status": "draft",
            "created_by": auth["user_id"],
            "updated_at": _now(),
        },
    )
    case = rows[0]
    await write_audit(
        auth,
        case_id=case["id"],
        client_id=client_id,
        action="case_created",
        entity_type="gst_9c_cases",
        entity_id=case["id"],
    )
    return case


async def update_case(auth: dict, case_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    case = await get_case(auth, case_id)
    allowed = {k: v for k, v in patch.items() if k in ("assigned_to", "notes", "status") and v is not None}
    if not allowed:
        return case
    allowed["updated_at"] = _now()
    rows = await SupabaseRest(auth).update("gst_9c_cases", {"id": f"eq.{case_id}"}, allowed)
    await write_audit(
        auth,
        case_id=case_id,
        client_id=case["client_id"],
        action="case_updated",
        entity_type="gst_9c_cases",
        entity_id=case_id,
        details=allowed,
    )
    return rows[0] if rows else case


async def approve_case(auth: dict, case_id: str) -> dict[str, Any]:
    case = await get_case(auth, case_id)
    db = SupabaseRest(auth)
    now = _now()
    rows = await db.update(
        "gst_9c_cases",
        {"id": f"eq.{case_id}"},
        {"status": "approved", "approved_by": auth["user_id"], "approved_at": now, "updated_at": now},
    )
    drafts = await db.select(
        "gst_9c_drafts",
        params={"case_id": f"eq.{case_id}", "order": "version.desc", "limit": "1"},
    )
    if drafts:
        await db.update(
            "gst_9c_drafts",
            {"id": f"eq.{drafts[0]['id']}"},
            {"status": "approved", "approved_by": auth["user_id"], "approved_at": now, "updated_at": now},
        )
    await write_audit(
        auth,
        case_id=case_id,
        client_id=case["client_id"],
        action="case_approved",
        entity_type="gst_9c_cases",
        entity_id=case_id,
    )
    return rows[0] if rows else case


async def case_dashboard_stats(auth: dict) -> dict[str, int]:
    cases = await list_cases(auth)
    docs = await SupabaseRest(auth).select("gst_9c_documents", params={"select": "id,status,client_id"})
    return {
        "total_cases": len(cases),
        "pending_documents": sum(1 for d in docs if d.get("status") == "pending"),
        "reconciling": sum(1 for c in cases if c.get("status") == "reconciling"),
        "awaiting_review": sum(1 for c in cases if c.get("status") in ("draft_ready", "in_review")),
        "completed": sum(1 for c in cases if c.get("status") in ("approved", "exported")),
    }
