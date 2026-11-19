from __future__ import annotations

from typing import Any

from .client import GstzenClient


async def call_return_api(path: str, body: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    return await GstzenClient().api_request(path, method=method, body=body)
