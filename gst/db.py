"""Thin Supabase PostgREST helpers."""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException


class SupabaseRest:
    def __init__(self, auth: dict):
        self.url = auth["supabase_url"].rstrip("/")
        self.jwt = auth["jwt"]
        self.anon_key = auth["anon_key"]
        self.service_key = auth["service_key"]

    def _headers(self, *, use_service: bool = False, prefer: str | None = None) -> dict[str, str]:
        key = self.service_key if use_service else self.anon_key
        token = self.service_key if use_service else self.jwt
        h = {
            "Authorization": f"Bearer {token}",
            "apikey": key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    async def select(
        self,
        table: str,
        *,
        params: dict[str, str] | None = None,
        use_service: bool = False,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.get(
                f"{self.url}/rest/v1/{table}",
                params=params or {},
                headers=self._headers(use_service=use_service),
            )
        if r.status_code >= 400:
            detail = r.text[:400]
            if "PGRST205" in detail or "Could not find the table" in detail:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Missing table public.{table}. Apply supabase/migrations/20261114_gst_9c.sql "
                        "in the FinAxis Supabase SQL Editor, then retry."
                    ),
                )
            raise HTTPException(status_code=502, detail=f"DB select {table} failed: {detail}")
        data = r.json()
        return data if isinstance(data, list) else []

    async def insert(
        self,
        table: str,
        row: dict[str, Any] | list[dict[str, Any]],
        *,
        use_service: bool = False,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post(
                f"{self.url}/rest/v1/{table}",
                headers=self._headers(use_service=use_service, prefer="return=representation"),
                json=row,
            )
        if r.status_code >= 400:
            detail = r.text[:400]
            if "PGRST205" in detail or "Could not find the table" in detail:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Missing table public.{table}. Apply supabase/migrations/20261114_gst_9c.sql "
                        "in the FinAxis Supabase SQL Editor, then retry."
                    ),
                )
            raise HTTPException(status_code=502, detail=f"DB insert {table} failed: {detail}")
        data = r.json()
        return data if isinstance(data, list) else [data]

    async def update(
        self,
        table: str,
        filters: dict[str, str],
        patch: dict[str, Any],
        *,
        use_service: bool = False,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.patch(
                f"{self.url}/rest/v1/{table}",
                params=filters,
                headers=self._headers(use_service=use_service, prefer="return=representation"),
                json=patch,
            )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"DB update {table} failed: {r.text[:400]}")
        data = r.json()
        return data if isinstance(data, list) else [data]

    async def delete(
        self,
        table: str,
        filters: dict[str, str],
        *,
        use_service: bool = False,
    ) -> None:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.delete(
                f"{self.url}/rest/v1/{table}",
                params=filters,
                headers=self._headers(use_service=use_service),
            )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"DB delete {table} failed: {r.text[:400]}")

    async def get_one(self, table: str, row_id: str, *, use_service: bool = False) -> dict[str, Any] | None:
        rows = await self.select(table, params={"id": f"eq.{row_id}", "limit": "1"}, use_service=use_service)
        return rows[0] if rows else None
