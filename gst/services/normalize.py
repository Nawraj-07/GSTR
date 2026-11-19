"""Normalize GSTZen payloads and Excel/CSV books into imported records."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _d(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(Decimal(str(v).replace(",", "").strip()))
    except (InvalidOperation, ValueError):
        return None


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def fingerprint(**parts: Any) -> str:
    raw = "|".join("" if p is None else str(p).strip().upper() for p in parts.values())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def records_from_return_payload(source: str, tax_period: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    root = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    if not isinstance(root, dict):
        return []
    out: list[dict[str, Any]] = []

    def add_b2b_like(section: Any, record_type: str = "invoice") -> None:
        if not isinstance(section, list):
            return
        for party in section:
            if not isinstance(party, dict):
                continue
            ctin = _s(party.get("ctin") or party.get("gstin"))
            invs = party.get("inv") or party.get("invoice") or party.get("nt") or []
            if isinstance(invs, dict):
                invs = [invs]
            for inv in invs if isinstance(invs, list) else []:
                if not isinstance(inv, dict):
                    continue
                inum = _s(inv.get("inum") or inv.get("nt_num") or inv.get("invoice_number"))
                idt = _date(inv.get("idt") or inv.get("nt_dt") or inv.get("invoice_date"))
                val = _d(inv.get("val") or inv.get("txval") or inv.get("taxable_value"))
                igst = cgst = sgst = cess = 0.0
                items = inv.get("itms") or []
                if isinstance(items, list):
                    for it in items:
                        det = (it or {}).get("itm_det") or (it or {}).get("itm") or it or {}
                        igst += _d(det.get("iamt")) or 0
                        cgst += _d(det.get("camt")) or 0
                        sgst += _d(det.get("samt")) or 0
                        cess += _d(det.get("csamt")) or 0
                        if val is None and det.get("txval") is not None:
                            val = (val or 0) + (_d(det.get("txval")) or 0)
                else:
                    igst = _d(inv.get("iamt") or inv.get("igst")) or 0
                    cgst = _d(inv.get("camt") or inv.get("cgst")) or 0
                    sgst = _d(inv.get("samt") or inv.get("sgst")) or 0
                    cess = _d(inv.get("csamt") or inv.get("cess")) or 0
                out.append(
                    {
                        "record_type": record_type,
                        "invoice_number": inum,
                        "invoice_date": idt,
                        "counterparty_gstin": ctin,
                        "taxable_value": val,
                        "igst": igst,
                        "cgst": cgst,
                        "sgst": sgst,
                        "cess": cess,
                        "total_tax": (igst or 0) + (cgst or 0) + (sgst or 0) + (cess or 0),
                        "raw": inv,
                        "fingerprint": fingerprint(
                            source=source, period=tax_period, gstin=ctin, inum=inum, idt=idt, val=val
                        ),
                    }
                )

    for key in ("b2b", "b2ba", "cdnr", "cdnra", "b2cl", "exp", "b2cs", "cdn", "impg", "impgsez"):
        if key in root:
            add_b2b_like(root.get(key), "credit_note" if "cdn" in key else "invoice")

    if source == "gstr3b":
        sup = root.get("sup_details") or root.get("rsup") or {}
        if isinstance(sup, dict) and sup:
            osup = sup.get("osup_det") or {}
            iamt = _d(osup.get("iamt"))
            camt = _d(osup.get("camt"))
            samt = _d(osup.get("samt"))
            csamt = _d(osup.get("csamt"))
            out.append(
                {
                    "record_type": "summary",
                    "invoice_number": f"3B-{tax_period}",
                    "invoice_date": None,
                    "counterparty_gstin": None,
                    "taxable_value": _d(osup.get("txval")),
                    "igst": iamt,
                    "cgst": camt,
                    "sgst": samt,
                    "cess": csamt,
                    "total_tax": (iamt or 0) + (camt or 0) + (samt or 0) + (csamt or 0),
                    "raw": sup,
                    "fingerprint": fingerprint(source=source, period=tax_period, kind="3b_osup"),
                }
            )

    if not out and root:
        out.append(
            {
                "record_type": "raw_period",
                "invoice_number": f"{source}-{tax_period}",
                "invoice_date": None,
                "counterparty_gstin": None,
                "taxable_value": None,
                "igst": None,
                "cgst": None,
                "sgst": None,
                "cess": None,
                "total_tax": None,
                "raw": {"keys": list(root.keys())[:50]},
                "fingerprint": fingerprint(source=source, period=tax_period, kind="raw"),
            }
        )
    return out


COLUMN_ALIASES = {
    "invoice_number": ["invoice_number", "invoice no", "invoice_no", "inv_no", "inum", "voucher no", "bill no"],
    "invoice_date": ["invoice_date", "invoice date", "date", "idt", "voucher date", "bill date"],
    "counterparty_gstin": ["gstin", "party_gstin", "supplier_gstin", "customer_gstin", "ctin", "counterparty_gstin"],
    "taxable_value": ["taxable_value", "taxable", "taxable amount", "taxable_amt", "txval", "assessable value", "net amount"],
    "igst": ["igst", "igst_amount", "iamt"],
    "cgst": ["cgst", "cgst_amount", "camt"],
    "sgst": ["sgst", "sgst_amount", "samt"],
    "cess": ["cess", "csamt", "cess_amount"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(h).strip().lower()).strip("_")


def map_row_headers(headers: list[str]) -> dict[str, int]:
    norm = [_norm_header(h) for h in headers]
    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        alias_set = {_norm_header(a) for a in aliases}
        for i, h in enumerate(norm):
            if h in alias_set or h.replace("_", "") in {a.replace("_", "") for a in alias_set}:
                mapping[field] = i
                break
    return mapping


def records_from_tabular(source: str, rows: list[list[Any]], headers: list[str] | None = None) -> list[dict[str, Any]]:
    if not rows:
        return []
    if headers is None:
        headers = [str(c) for c in rows[0]]
        data_rows = rows[1:]
    else:
        data_rows = rows
    mapping = map_row_headers(headers)
    out: list[dict[str, Any]] = []
    for row in data_rows:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        def get(field: str) -> Any:
            idx = mapping.get(field)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        inum = _s(get("invoice_number"))
        idt = _date(get("invoice_date"))
        ctin = _s(get("counterparty_gstin"))
        if ctin:
            ctin = ctin.upper()
        txval = _d(get("taxable_value"))
        igst = _d(get("igst")) or 0
        cgst = _d(get("cgst")) or 0
        sgst = _d(get("sgst")) or 0
        cess = _d(get("cess")) or 0
        if not inum and txval is None:
            continue
        out.append(
            {
                "record_type": "invoice",
                "invoice_number": inum,
                "invoice_date": idt,
                "counterparty_gstin": ctin,
                "taxable_value": txval,
                "igst": igst,
                "cgst": cgst,
                "sgst": sgst,
                "cess": cess,
                "total_tax": igst + cgst + sgst + cess,
                "raw": {"headers": headers, "row": [str(c) if c is not None else "" for c in row[:30]]},
                "fingerprint": fingerprint(source=source, gstin=ctin, inum=inum, idt=idt, val=txval),
            }
        )
    return out
