from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


def parse_bytes(filename: str, content: bytes) -> tuple[list[str], list[list[Any]]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = [list(r) for r in reader]
        if not rows:
            return [], []
        return [str(h) for h in rows[0]], rows[1:]

    if name.endswith(".xlsx") or name.endswith(".xls"):
        from openpyxl import load_workbook

        wb = load_workbook(filename=io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], []
        headers = ["" if h is None else str(h) for h in header_row]
        return headers, [list(r) for r in rows_iter]

    raise ValueError("Unsupported file type. Upload Excel (.xlsx) or CSV.")


def parse_file(path: Path) -> tuple[list[str], list[list[Any]]]:
    return parse_bytes(path.name, path.read_bytes())
