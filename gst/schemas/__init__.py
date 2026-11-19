"""Pydantic request/response schemas."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "gstr9c"


class ValidateGstinRequest(BaseModel):
    gstin: str = Field(..., min_length=15, max_length=15)
    client_id: str | None = None


class ValidateGstinResponse(BaseModel):
    gstin: str
    ok: bool
    raw: dict


class CaseCreateRequest(BaseModel):
    client_id: str
    registration_id: str
    financial_year: str
    assigned_to: str | None = None
    notes: str | None = None
    validate_gstin: bool = True


class CaseUpdateRequest(BaseModel):
    assigned_to: str | None = None
    notes: str | None = None
    status: str | None = None


class FetchReturnsRequest(BaseModel):
    return_types: list[str] = Field(default_factory=lambda: ["gstr1", "gstr3b", "gstr2b"])
    tax_periods: list[str] = Field(default_factory=list)


class ReconcileRequest(BaseModel):
    comparison_types: list[str] = Field(
        default_factory=lambda: [
            "gstr1_vs_sales",
            "gstr3b_vs_gstr1",
            "gstr2b_vs_purchases",
            "books_vs_returns",
        ]
    )


class AdjustmentRequest(BaseModel):
    table_code: str | None = None
    field_key: str | None = None
    amount: Decimal = Decimal("0")
    explanation: str


class GenerateRequest(BaseModel):
    fy_schema_key: str | None = None


class ExportRequest(BaseModel):
    export_type: str = "gstr9c_excel"


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None
