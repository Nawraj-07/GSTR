"""Deterministic reconciliation engine."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

TWOPLACES = Decimal("0.01")


def D(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    return Decimal(str(v)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _key(rec: dict[str, Any]) -> str:
    fp = rec.get("fingerprint")
    if fp:
        return str(fp)
    return "|".join(
        [
            (rec.get("invoice_number") or "").strip().upper(),
            (rec.get("counterparty_gstin") or "").strip().upper(),
            str(rec.get("invoice_date") or ""),
            str(D(rec.get("taxable_value"))),
        ]
    )


def _soft_key(rec: dict[str, Any]) -> str:
    return "|".join(
        [
            (rec.get("invoice_number") or "").strip().upper(),
            (rec.get("counterparty_gstin") or "").strip().upper(),
        ]
    )


def compare_sets(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    left_label: str,
    right_label: str,
    amount_tolerance: Decimal = Decimal("1.00"),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    right_by_key = {_key(r): r for r in right}
    right_by_soft: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in right:
        right_by_soft[_soft_key(r)].append(r)
    used_right: set[str] = set()

    for l in left:
        if l.get("record_type") in ("raw_period",):
            continue
        lk = _key(l)
        match = right_by_key.get(lk)
        if match:
            used_right.add(_key(match))
            diff = D(l.get("taxable_value")) - D(match.get("taxable_value"))
            tax_diff = D(l.get("total_tax")) - D(match.get("total_tax"))
            if abs(diff) <= amount_tolerance and abs(tax_diff) <= amount_tolerance:
                status = "matched"
            elif abs(diff) <= amount_tolerance * 10 or _soft_key(l) == _soft_key(match):
                status = "partially_matched"
            else:
                status = "mismatched"
            items.append(
                {
                    "match_status": status,
                    "difference_type": "taxable_value" if diff else "tax",
                    "difference_amount": float(diff),
                    "left_record_id": l.get("id"),
                    "right_record_id": match.get("id"),
                    "explanation": f"{left_label} vs {right_label}",
                    "meta": {
                        "invoice_number": l.get("invoice_number"),
                        "left_taxable": float(D(l.get("taxable_value"))),
                        "right_taxable": float(D(match.get("taxable_value"))),
                    },
                }
            )
            continue
        softs = right_by_soft.get(_soft_key(l), [])
        soft = next((s for s in softs if _key(s) not in used_right), None)
        if soft:
            used_right.add(_key(soft))
            diff = D(l.get("taxable_value")) - D(soft.get("taxable_value"))
            items.append(
                {
                    "match_status": "partially_matched",
                    "difference_type": "amount_or_date",
                    "difference_amount": float(diff),
                    "left_record_id": l.get("id"),
                    "right_record_id": soft.get("id"),
                    "explanation": f"Soft match ({left_label} vs {right_label})",
                    "meta": {"invoice_number": l.get("invoice_number")},
                }
            )
            continue
        items.append(
            {
                "match_status": "missing_in_books",
                "difference_type": "missing",
                "difference_amount": float(D(l.get("taxable_value"))),
                "left_record_id": l.get("id"),
                "right_record_id": None,
                "explanation": f"Present in {left_label}, missing in {right_label}",
                "meta": {"invoice_number": l.get("invoice_number")},
            }
        )

    for r in right:
        if r.get("record_type") in ("raw_period",) or _key(r) in used_right:
            continue
        items.append(
            {
                "match_status": "missing_in_gst",
                "difference_type": "missing",
                "difference_amount": float(D(r.get("taxable_value"))),
                "left_record_id": None,
                "right_record_id": r.get("id"),
                "explanation": f"Present in {right_label}, missing in {left_label}",
                "meta": {"invoice_number": r.get("invoice_number")},
            }
        )

    summary = {
        "total": len(items),
        "matched": sum(1 for i in items if i["match_status"] == "matched"),
        "partially_matched": sum(1 for i in items if i["match_status"] == "partially_matched"),
        "mismatched": sum(1 for i in items if i["match_status"] == "mismatched"),
        "missing_in_gst": sum(1 for i in items if i["match_status"] == "missing_in_gst"),
        "missing_in_books": sum(1 for i in items if i["match_status"] == "missing_in_books"),
        "net_difference": float(sum(D(i.get("difference_amount")) for i in items)),
        "left_label": left_label,
        "right_label": right_label,
    }
    return items, summary


def sum_taxable(records: list[dict[str, Any]]) -> Decimal:
    return sum((D(r.get("taxable_value")) for r in records if r.get("record_type") != "raw_period"), Decimal("0"))


def compare_totals(left, right, *, left_label, right_label):
    lt = sum_taxable(left)
    rt = sum_taxable(right)
    diff = lt - rt
    status = "matched" if abs(diff) <= Decimal("1.00") else "mismatched"
    items = [
        {
            "match_status": status,
            "difference_type": "period_total",
            "difference_amount": float(diff),
            "left_record_id": None,
            "right_record_id": None,
            "explanation": f"Total taxable {left_label} ({lt}) vs {right_label} ({rt})",
            "meta": {"left_total": float(lt), "right_total": float(rt)},
        }
    ]
    summary = {
        "total": 1,
        "matched": 1 if status == "matched" else 0,
        "partially_matched": 0,
        "mismatched": 0 if status == "matched" else 1,
        "missing_in_gst": 0,
        "missing_in_books": 0,
        "net_difference": float(diff),
        "left_label": left_label,
        "right_label": right_label,
    }
    return items, summary
