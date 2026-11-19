"""GSTR-9C monetary calculations using Decimal."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from gst.reconciliation.engine import D, sum_taxable


def _val(amount: Decimal, sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {"value": float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), "source_refs": sources}


def calculate_table_values(*, case, records_by_source, adjustments, schema) -> list[dict[str, Any]]:
    sales_books = records_by_source.get("sales_register", [])
    purchases_books = records_by_source.get("purchase_register", [])
    gstr1 = records_by_source.get("gstr1", [])
    gstr3b = records_by_source.get("gstr3b", [])
    gstr2b = records_by_source.get("gstr2b", []) or records_by_source.get("gstr2a", [])
    gstr9 = records_by_source.get("gstr9", [])
    pnl = records_by_source.get("profit_and_loss", [])
    tb = records_by_source.get("trial_balance", [])

    turnover_books = sum_taxable(sales_books) or sum_taxable(pnl) or sum_taxable(tb)
    turnover_returns = sum_taxable(gstr1) or sum_taxable(gstr3b)
    turnover_gstr9 = sum_taxable(gstr9) or turnover_returns
    itc_books = sum((D(r.get("igst")) + D(r.get("cgst")) + D(r.get("sgst")) + D(r.get("cess")) for r in purchases_books), Decimal("0"))
    itc_returns = sum((D(r.get("igst")) + D(r.get("cgst")) + D(r.get("sgst")) + D(r.get("cess")) for r in gstr2b), Decimal("0"))
    tax_books_igst = sum((D(r.get("igst")) for r in sales_books), Decimal("0"))
    tax_books_cgst = sum((D(r.get("cgst")) for r in sales_books), Decimal("0"))
    tax_books_sgst = sum((D(r.get("sgst")) for r in sales_books), Decimal("0"))
    tax_books_cess = sum((D(r.get("cess")) for r in sales_books), Decimal("0"))
    tax_returns = sum((D(r.get("igst")) + D(r.get("cgst")) + D(r.get("sgst")) + D(r.get("cess")) for r in gstr3b), Decimal("0"))

    adj_map: dict[str, Decimal] = {}
    for a in adjustments:
        key = f"{a.get('table_code') or ''}:{a.get('field_key') or ''}"
        adj_map[key] = adj_map.get(key, Decimal("0")) + D(a.get("amount"))

    def adj(table: str, row: str) -> Decimal:
        return adj_map.get(f"{table}:{row}", Decimal("0"))

    computed: dict[tuple[str, str], dict[str, Any]] = {}
    computed[("pt_i", "fy")] = {"value_text": case.get("financial_year"), "value": None, "source_refs": []}
    computed[("pt_i", "gstin")] = {"value_text": case.get("gstin"), "value": None, "source_refs": []}
    computed[("pt_i", "legal_name")] = {"value_text": None, "value": None, "source_refs": []}

    five_a = turnover_books + adj("pt_ii_5", "5a")
    five_g = turnover_returns + adj("pt_ii_5", "5g")
    five_k = adj("pt_ii_5", "5k")
    five_n = five_a + five_k
    five_o = turnover_gstr9 + adj("pt_ii_5", "5o")
    five_p = five_n - five_o
    computed[("pt_ii_5", "5a")] = _val(five_a, [{"source": "sales_register/pnl"}])
    for rk in ("5b", "5c", "5d", "5e", "5f", "5h", "5i", "5j"):
        computed[("pt_ii_5", rk)] = _val(adj("pt_ii_5", rk), [{"source": "adjustment"}])
    computed[("pt_ii_5", "5g")] = _val(five_g, [{"source": "gstr1/gstr3b"}])
    computed[("pt_ii_5", "5k")] = _val(five_k, [{"source": "adjustment"}])
    computed[("pt_ii_5", "5n")] = _val(five_n, [{"source": "derived"}])
    computed[("pt_ii_5", "5o")] = _val(five_o, [{"source": "gstr9_or_returns"}])
    computed[("pt_ii_5", "5p")] = _val(five_p, [{"source": "derived"}])

    computed[("pt_iii_9", "9a")] = _val(turnover_books, [{"source": "sales_register"}])
    computed[("pt_iii_9", "9b")] = _val(tax_books_igst + adj("pt_iii_9", "9b"), [{"source": "sales_register"}])
    computed[("pt_iii_9", "9c")] = _val(tax_books_cgst + adj("pt_iii_9", "9c"), [{"source": "sales_register"}])
    computed[("pt_iii_9", "9d")] = _val(tax_books_sgst + adj("pt_iii_9", "9d"), [{"source": "sales_register"}])
    computed[("pt_iii_9", "9e")] = _val(tax_books_cess + adj("pt_iii_9", "9e"), [{"source": "sales_register"}])
    computed[("pt_iii_9", "9f")] = _val(tax_returns + adj("pt_iii_9", "9f"), [{"source": "gstr3b"}])
    books_tax_total = tax_books_igst + tax_books_cgst + tax_books_sgst + tax_books_cess
    computed[("pt_iii_9", "9g")] = _val(books_tax_total - tax_returns, [{"source": "derived"}])

    twelve_a = itc_books + adj("pt_iv_12", "12a")
    twelve_e = itc_returns + adj("pt_iv_12", "12e")
    computed[("pt_iv_12", "12a")] = _val(twelve_a, [{"source": "purchase_register"}])
    for rk in ("12b", "12c"):
        computed[("pt_iv_12", rk)] = _val(adj("pt_iv_12", rk), [{"source": "adjustment"}])
    computed[("pt_iv_12", "12d")] = _val(twelve_a + adj("pt_iv_12", "12b") - adj("pt_iv_12", "12c"), [{"source": "derived"}])
    computed[("pt_iv_12", "12e")] = _val(twelve_e, [{"source": "gstr2b"}])
    computed[("pt_iv_12", "12f")] = _val(D(computed[("pt_iv_12", "12d")]["value"]) - twelve_e, [{"source": "derived"}])
    for rk in ("v_tax", "v_interest", "v_penalty", "v_other"):
        computed[("pt_v", rk)] = _val(adj("pt_v", rk), [{"source": "adjustment"}])

    rows_out = []
    for table in schema.get("tables", []):
        tcode = table["table_code"]
        for row in table.get("rows", []):
            rk = row["row_key"]
            cell = computed.get((tcode, rk), {"value": None, "value_text": None, "source_refs": []})
            rows_out.append(
                {
                    "table_code": tcode,
                    "row_key": rk,
                    "col_key": "amount",
                    "value": cell.get("value"),
                    "value_text": cell.get("value_text"),
                    "source_refs": cell.get("source_refs") or [],
                }
            )
    return rows_out


def validate_draft_values(values: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings = []
    by_key = {(v["table_code"], v["row_key"]): v for v in values}
    five_p = by_key.get(("pt_ii_5", "5p"))
    if five_p and five_p.get("value") is not None and abs(float(five_p["value"])) > 1:
        warnings.append({"code": "turnover_unreconciled", "message": f"Unreconciled turnover (5P) is {five_p['value']}."})
    twelve_f = by_key.get(("pt_iv_12", "12f"))
    if twelve_f and twelve_f.get("value") is not None and abs(float(twelve_f["value"])) > 1:
        warnings.append({"code": "itc_unreconciled", "message": f"Unreconciled ITC (12F) is {twelve_f['value']}."})
    return warnings
