from __future__ import annotations

from typing import Any

from gst.db import SupabaseRest


async def write_audit(
    auth: dict,
    *,
    action: str,
    case_id: str | None = None,
    client_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        await SupabaseRest(auth).insert(
            "gst_audit_logs",
            {
                "case_id": case_id,
                "client_id": client_id,
                "actor_id": auth.get("user_id"),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details or {},
            },
        )
    except Exception:
        pass
