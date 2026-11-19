"""FY-specific GSTR-9C table mapping (generic MVP pack)."""
from __future__ import annotations

from typing import Any

GENERIC_TABLES: list[dict[str, Any]] = [
    {
        "table_code": "pt_i",
        "title": "Part I — Basic Details",
        "rows": [
            {"row_key": "fy", "label": "Financial Year"},
            {"row_key": "gstin", "label": "GSTIN"},
            {"row_key": "legal_name", "label": "Legal Name"},
        ],
    },
    {
        "table_code": "pt_ii_5",
        "title": "Part II — Reconciliation of turnover",
        "rows": [
            {"row_key": "5a", "label": "Turnover as per audited financial statements"},
            {"row_key": "5b", "label": "Unbilled revenue at beginning of FY"},
            {"row_key": "5c", "label": "Unadjusted advances at beginning of FY"},
            {"row_key": "5d", "label": "Deemed supply under Schedule I"},
            {"row_key": "5e", "label": "Credit notes in books but not in returns"},
            {"row_key": "5f", "label": "Trade discounts not permissible"},
            {"row_key": "5g", "label": "Turnover declared in returns"},
            {"row_key": "5h", "label": "Unbilled revenue at end of FY"},
            {"row_key": "5i", "label": "Unadjusted advances at end of FY"},
            {"row_key": "5j", "label": "Credit notes in returns but not in books"},
            {"row_key": "5k", "label": "Adjustments (+/-) — others"},
            {"row_key": "5n", "label": "Annual turnover after adjustments"},
            {"row_key": "5o", "label": "Turnover as declared in GSTR-9"},
            {"row_key": "5p", "label": "Unreconciled turnover (5n - 5o)"},
        ],
    },
    {
        "table_code": "pt_iii_9",
        "title": "Part III — Reconciliation of tax paid",
        "rows": [
            {"row_key": "9a", "label": "Taxable value as per books"},
            {"row_key": "9b", "label": "Tax payable as per books (IGST)"},
            {"row_key": "9c", "label": "Tax payable as per books (CGST)"},
            {"row_key": "9d", "label": "Tax payable as per books (SGST)"},
            {"row_key": "9e", "label": "Tax payable as per books (Cess)"},
            {"row_key": "9f", "label": "Tax paid as declared in annual return"},
            {"row_key": "9g", "label": "Unreconciled tax payable"},
        ],
    },
    {
        "table_code": "pt_iv_12",
        "title": "Part IV — Reconciliation of ITC",
        "rows": [
            {"row_key": "12a", "label": "ITC availed as per audited financials"},
            {"row_key": "12b", "label": "ITC booked earlier claimed now"},
            {"row_key": "12c", "label": "ITC booked now to claim later"},
            {"row_key": "12d", "label": "ITC available as per books"},
            {"row_key": "12e", "label": "ITC claimed in GSTR-9"},
            {"row_key": "12f", "label": "Unreconciled ITC"},
        ],
    },
    {
        "table_code": "pt_v",
        "title": "Part V — Auditor recommendations",
        "rows": [
            {"row_key": "v_tax", "label": "Additional tax liability"},
            {"row_key": "v_interest", "label": "Interest"},
            {"row_key": "v_penalty", "label": "Penalty"},
            {"row_key": "v_other", "label": "Others"},
        ],
    },
]


def schema_for_fy(fy: str) -> dict[str, Any]:
    return {
        "fy_schema_key": f"generic:{fy}",
        "disclaimer": (
            "Generic GSTR-9C table map for draft preparation only. "
            "Verify against the official form for this FY before filing."
        ),
        "tables": GENERIC_TABLES,
    }
