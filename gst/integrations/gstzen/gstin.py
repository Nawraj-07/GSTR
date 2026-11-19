from __future__ import annotations

from typing import Any

from .client import GstzenClient


async def validate_gstin(gstin: str) -> dict[str, Any]:
    return await GstzenClient().validate_gstin(gstin)
