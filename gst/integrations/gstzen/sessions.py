from __future__ import annotations

from typing import Any

from .client import GstzenClient


async def generate_otp(payload: dict[str, Any]) -> dict[str, Any]:
    return await GstzenClient().api_request("gstn-generate-otp/", body=payload)


async def establish_session(payload: dict[str, Any]) -> dict[str, Any]:
    return await GstzenClient().api_request("gstn-establish-session/", body=payload)


async def refresh_session(payload: dict[str, Any]) -> dict[str, Any]:
    return await GstzenClient().api_request("gstn-refresh-session/", body=payload)


async def check_session(payload: dict[str, Any]) -> dict[str, Any]:
    return await GstzenClient().api_request("gstn-check-session/", body=payload)
