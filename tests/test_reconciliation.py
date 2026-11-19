from decimal import Decimal

from gst.calculations.engine import calculate_table_values, validate_draft_values
from gst.calculations.fy_rules import schema_for_fy
from gst.reconciliation.engine import D, compare_sets, compare_totals
from gst.services.fy import fy_tax_periods, normalize_fy
from gst.services.normalize import fingerprint, records_from_tabular


def test_fy_periods():
    periods = fy_tax_periods("2024-25")
    assert periods[0] == "042024"
    assert periods[-1] == "032025"
    assert len(periods) == 12
    assert normalize_fy("FY2024-2025") == "2024-25"


def test_compare_sets_matched_and_missing():
    left = [
        {"id": "1", "invoice_number": "INV1", "counterparty_gstin": "29AAAAA0000A1Z5", "invoice_date": "2024-05-01", "taxable_value": 100, "total_tax": 18, "fingerprint": "a"},
        {"id": "2", "invoice_number": "INV2", "counterparty_gstin": "29AAAAA0000A1Z5", "invoice_date": "2024-05-02", "taxable_value": 50, "total_tax": 9, "fingerprint": "b"},
    ]
    right = [
        {"id": "3", "invoice_number": "INV1", "counterparty_gstin": "29AAAAA0000A1Z5", "invoice_date": "2024-05-01", "taxable_value": 100, "total_tax": 18, "fingerprint": "a"},
    ]
    items, summary = compare_sets(left, right, left_label="GSTR-1", right_label="Sales")
    assert summary["matched"] == 1
    assert summary["missing_in_books"] == 1


def test_compare_totals():
    items, summary = compare_totals(
        [{"taxable_value": 100}, {"taxable_value": 40}],
        [{"taxable_value": 140}],
        left_label="A",
        right_label="B",
    )
    assert summary["matched"] == 1
    assert items[0]["difference_amount"] == 0.0


def test_tabular_normalize():
    headers = ["Invoice No", "Date", "GSTIN", "Taxable Value", "IGST", "CGST", "SGST"]
    rows = [["A1", "01-05-2024", "29AAAAA0000A1Z5", "1000", "180", "0", "0"]]
    recs = records_from_tabular("sales_register", rows, headers=headers)
    assert len(recs) == 1
    assert recs[0]["invoice_number"] == "A1"
    assert recs[0]["taxable_value"] == 1000.0


def test_9c_calculation_and_warnings():
    schema = schema_for_fy("2024-25")
    case = {"financial_year": "2024-25", "gstin": "29AAAAA0000A1Z5"}
    records = {
        "sales_register": [{"taxable_value": 1000, "igst": 180, "cgst": 0, "sgst": 0, "cess": 0}],
        "gstr1": [{"taxable_value": 900, "igst": 162, "cgst": 0, "sgst": 0, "cess": 0}],
        "gstr3b": [{"taxable_value": 900, "igst": 162, "cgst": 0, "sgst": 0, "cess": 0, "record_type": "summary"}],
        "purchase_register": [{"igst": 50, "cgst": 0, "sgst": 0, "cess": 0, "taxable_value": 200}],
        "gstr2b": [{"igst": 40, "cgst": 0, "sgst": 0, "cess": 0, "taxable_value": 180}],
    }
    values = calculate_table_values(case=case, records_by_source=records, adjustments=[], schema=schema)
    warnings = validate_draft_values(values)
    assert any(w["code"] == "turnover_unreconciled" for w in warnings)


def test_decimal_helper():
    assert D("10.005") == Decimal("10.01")
    assert fingerprint(a="x", b="y")
