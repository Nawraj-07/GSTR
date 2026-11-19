from __future__ import annotations

from .client import GstzenClient


async def login_for_access_token() -> str:
    return await GstzenClient().get_bearer_token()
