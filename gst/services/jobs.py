from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from gst.auth import require_client_access
from gst.db import SupabaseRest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_job(
    auth: dict,
    *,
    client_id: str,
    job_type: str,
    case_id: str | None = None,
    registration_id: str | None = None,
    input_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await require_client_access(auth, client_id)
    rows = await SupabaseRest(auth).insert(
        "gst_import_jobs",
        {
            "case_id": case_id,
            "client_id": client_id,
            "registration_id": registration_id,
            "job_type": job_type,
            "status": "queued",
            "progress": 0,
            "input": input_payload or {},
            "result": {},
            "created_by": auth["user_id"],
            "updated_at": _now(),
        },
    )
    return rows[0]


async def get_job(auth: dict, job_id: str) -> dict[str, Any]:
    job = await SupabaseRest(auth).get_one("gst_import_jobs", job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await require_client_access(auth, job["client_id"])
    return job


async def set_job_status(
    auth: dict,
    job_id: str,
    *,
    status: str,
    progress: float | None = None,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> dict[str, Any]:
    patch: dict[str, Any] = {"status": status, "updated_at": _now()}
    if progress is not None:
        patch["progress"] = progress
    if result is not None:
        patch["result"] = result
    if error_message is not None:
        patch["error_message"] = error_message
    if started:
        patch["started_at"] = _now()
    if finished:
        patch["finished_at"] = _now()
    rows = await SupabaseRest(auth).update("gst_import_jobs", {"id": f"eq.{job_id}"}, patch, use_service=True)
    return rows[0] if rows else await get_job(auth, job_id)
