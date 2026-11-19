"""Supabase JWT auth + client access checks."""
from __future__ import annotations

import os

import httpx
from fastapi import HTTPException


async def require_employee_or_admin(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")

    jwt = authorization.split(" ", 1)[1].strip()
    supabase_url = (os.getenv("SUPABASE_URL", "") or os.getenv("VITE_SUPABASE_URL", "")).rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("VITE_SUPABASE_ANON_KEY", "")
    if not supabase_url or not service_key:
        raise HTTPException(status_code=503, detail="SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    if not anon_key:
        raise HTTPException(status_code=503, detail="SUPABASE_ANON_KEY not configured")

    async with httpx.AsyncClient(timeout=20) as http:
        u = await http.get(
            f"{supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {jwt}", "apikey": anon_key},
        )
    if u.status_code >= 400:
        try:
            details = u.json()
        except Exception:
            details = {"status": u.status_code, "body": u.text}
        raise HTTPException(status_code=401, detail=f"Invalid session: {details}")

    user = u.json()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    async with httpx.AsyncClient(timeout=20) as http:
        p = await http.get(
            f"{supabase_url}/rest/v1/profiles",
            params={"select": "id,role,is_active,workspace_id", "id": f"eq.{user_id}", "limit": "1"},
            headers={
                "Authorization": f"Bearer {jwt}",
                "apikey": anon_key,
                "Accept": "application/json",
            },
        )
        if p.status_code >= 400:
            p = await http.get(
                f"{supabase_url}/rest/v1/profiles",
                params={"select": "id,role,is_active,workspace_id", "id": f"eq.{user_id}", "limit": "1"},
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "apikey": service_key,
                    "Accept": "application/json",
                },
            )
    if p.status_code >= 400:
        try:
            detail = p.json()
        except Exception:
            detail = {"status": p.status_code, "body": p.text}
        raise HTTPException(status_code=401, detail=f"Profile lookup failed: {detail}")

    rows = p.json() or []
    if not rows:
        raise HTTPException(status_code=401, detail="Profile not found")

    profile = rows[0]
    role = profile.get("role")
    if profile.get("is_active") is False:
        raise HTTPException(status_code=403, detail="User is inactive")
    if role not in ("employee", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "user_id": user_id,
        "role": role,
        "workspace_id": profile.get("workspace_id"),
        "jwt": jwt,
        "anon_key": anon_key,
        "service_key": service_key,
        "supabase_url": supabase_url,
    }


async def require_client_access(auth: dict, client_id: str) -> None:
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    if auth.get("role") == "admin":
        return

    supabase_url = auth["supabase_url"]
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(
            f"{supabase_url}/rest/v1/rpc/employee_has_client_access",
            headers={
                "Authorization": f"Bearer {auth['jwt']}",
                "apikey": auth["anon_key"],
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"emp": auth["user_id"], "client": client_id},
        )
        if r.status_code >= 400:
            r = await http.post(
                f"{supabase_url}/rest/v1/rpc/employee_has_client_access",
                headers={
                    "Authorization": f"Bearer {auth['service_key']}",
                    "apikey": auth["service_key"],
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"emp": auth["user_id"], "client": client_id},
            )

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Access check failed")
    if r.json() is not True:
        raise HTTPException(status_code=403, detail="No access to this client")
