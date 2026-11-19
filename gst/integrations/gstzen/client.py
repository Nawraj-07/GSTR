"""Reusable GSTZen HTTP client."""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

GSTZEN_VALIDATOR_URL = "https://my.gstzen.in/api/gstin-validator/"
GSTZEN_API_BASE = "https://my.gstzen.in/api/"
GSTZEN_JWT_URL = "https://my.gstzen.in/accounts/api/login/token/"

ALLOWED_API_PREFIXES = (
    "gstn-generate-otp",
    "gstn-establish-session",
    "gstn-refresh-session",
    "gstn-check-session",
    "gstn-generate-evc-otp",
    "gstr1",
    "gstr1a",
    "gstr2",
    "gstr3b",
    "ims",
    "file-details",
    "file-download",
    "file_details",
    "file_download",
    "cdn",
    "imports",
    "isd",
    "tds",
    "tcs",
    "ecommerce",
    "e-commerce",
)

PENDING_VERIFICATION_PREFIXES = ("gstr9", "gstr9c")


class GstzenError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class GstzenClient:
    def __init__(self) -> None:
        self.api_key = (os.getenv("GSTZEN_API_KEY") or "").strip()
        self.username = (os.getenv("GSTZEN_USERNAME") or os.getenv("GSTZEN_EMAIL") or "").strip()
        self.password = (os.getenv("GSTZEN_PASSWORD") or "").strip()
        self._access_token: str | None = None
        self._access_expiry = 0.0

    def _assert_allowed_path(self, path: str) -> None:
        cleaned = path.replace("\\", "/").lstrip("/").lower()
        if not cleaned or ".." in cleaned:
            raise GstzenError("Invalid GSTZen API path")
        for pending in PENDING_VERIFICATION_PREFIXES:
            if cleaned == pending or cleaned.startswith(f"{pending}/") or cleaned.startswith(f"{pending}?"):
                raise GstzenError(
                    f"GSTZen path '{path}' is pending verification — not enabled yet",
                    status_code=501,
                )
        if not any(
            cleaned == p or cleaned.startswith(f"{p}/") or cleaned.startswith(f"{p}?")
            for p in ALLOWED_API_PREFIXES
        ):
            raise GstzenError(f"GSTZen path '{path}' is not allowlisted", status_code=400)

    async def validate_gstin(self, gstin: str) -> dict[str, Any]:
        if not self.api_key:
            raise GstzenError("GSTZEN_API_KEY not configured", status_code=503)
        gstin = (gstin or "").strip().upper()
        if len(gstin) != 15:
            raise GstzenError("GSTIN must be 15 characters", status_code=400)
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post(
                GSTZEN_VALIDATOR_URL,
                headers={"Token": self.api_key, "Content-Type": "application/json"},
                json={"gstin": gstin},
            )
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            raise GstzenError(f"GSTIN validation failed ({r.status_code})", status_code=r.status_code, payload=data)
        return data if isinstance(data, dict) else {"data": data}

    async def get_bearer_token(self) -> str:
        if not self.username or not self.password:
            raise GstzenError("GSTZEN_USERNAME / GSTZEN_PASSWORD not configured", status_code=503)
        now = time.time()
        if self._access_token and now < self._access_expiry - 60:
            return self._access_token
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post(
                GSTZEN_JWT_URL,
                headers={"Content-Type": "application/json"},
                json={"username": self.username, "password": self.password},
            )
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code >= 400:
            raise GstzenError("GSTZen login failed", status_code=r.status_code, payload=data)
        token = data.get("access") or data.get("access_token") or data.get("token")
        if not token:
            raise GstzenError("GSTZen login response missing access token", status_code=502, payload=data)
        self._access_token = str(token)
        self._access_expiry = now + float(data.get("expires_in") or 86_400)
        return self._access_token

    async def api_request(
        self,
        path: str,
        *,
        method: str = "POST",
        body: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_allowed_path(path)
        token = await self.get_bearer_token()
        url = f"{GSTZEN_API_BASE}{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=90) as http:
            r = await http.request(
                method.upper(),
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=body if body is not None else {},
            )
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        if r.status_code >= 400:
            raise GstzenError(f"GSTZen API failed ({r.status_code})", status_code=r.status_code, payload=data)
        if isinstance(data, dict) and data.get("status") == 0:
            raise GstzenError("GSTZen business error (status=0)", status_code=502, payload=data)
        return data if isinstance(data, dict) else {"data": data}
