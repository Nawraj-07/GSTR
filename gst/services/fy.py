"""Financial year helpers (India: Apr–Mar)."""
from __future__ import annotations

import re


def parse_fy(fy: str) -> tuple[int, int]:
    s = fy.strip().upper().replace("FY", "").strip()
    m = re.match(r"^(\d{4})\s*[-/]\s*(\d{2}|\d{4})$", s)
    if not m:
        raise ValueError(f"Invalid financial year: {fy}")
    start = int(m.group(1))
    end_raw = m.group(2)
    end = int(end_raw) if len(end_raw) == 4 else 2000 + int(end_raw)
    if end != start + 1 and len(end_raw) == 2:
        end = start + 1
    elif end != start + 1:
        raise ValueError(f"Financial year end must be start+1: {fy}")
    return start, end


def fy_tax_periods(fy: str) -> list[str]:
    start, end = parse_fy(fy)
    periods: list[str] = []
    for month in range(4, 13):
        periods.append(f"{month:02d}{start}")
    for month in range(1, 4):
        periods.append(f"{month:02d}{end}")
    return periods


def normalize_fy(fy: str) -> str:
    start, end = parse_fy(fy)
    return f"{start}-{str(end)[-2:]}"
