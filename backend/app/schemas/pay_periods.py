from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CATEGORIES = Literal[
    "Ordinary",
    "Overtime",
    "Saturday",
    "Sunday",
    "Public holiday",
    "Leave",
    "Allowance",
    "Bonus",
    "Deduction",
    "Other",
]


class PayslipItemInput(BaseModel):
    id: str | None = None
    category: CATEGORIES = "Other"
    description: str = ""
    hours: Decimal | None = Field(default=None, ge=0)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    amount: Decimal | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    source_text: str | None = None
    verified: bool = False

    @field_validator("hourly_rate")
    @classmethod
    def plausible_rate(cls, value: Decimal | None) -> Decimal | None:
        return value


class PayslipInput(BaseModel):
    employee_name: str | None = None
    payment_date: date | None = None
    gross_pay: Decimal | None = None
    net_pay: Decimal | None = None
    tax_withheld: Decimal | None = None
    superannuation: Decimal | None = None
    total_paid_hours: Decimal | None = None
    deductions: Decimal | None = None
    allowances: Decimal | None = None
    notes: str | None = None
    verified: bool = False
    items: list[PayslipItemInput] = Field(default_factory=list)


class ShiftPunchInput(BaseModel):
    id: str | None = None
    sequence: int = Field(default=0, ge=0)
    in_time: time | None = None
    out_time: time | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    verified: bool = False


class ShiftInput(BaseModel):
    id: str | None = None
    source_screenshot_id: str | None = None
    shift_date: date | None = None
    start_time: time | None = None
    finish_time: time | None = None
    unpaid_break_minutes: int = Field(default=0, ge=0, le=1440)
    total_worked_hours: Decimal | None = Field(default=None, ge=0)
    category: CATEGORIES = "Ordinary"
    confidence_score: int = Field(default=0, ge=0, le=100)
    verified: bool = False
    punches: list[ShiftPunchInput] = Field(default_factory=list)


class PayPeriodCreate(BaseModel):
    employer_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    payslip: PayslipInput = Field(default_factory=PayslipInput)
    shifts: list[ShiftInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> "PayPeriodCreate":
        return self


class PayPeriodUpdate(PayPeriodCreate):
    pass


class FileInfo(BaseModel):
    id: str
    original_filename: str | None
    preview_url: str


class PayPeriodSummary(BaseModel):
    id: str
    employer_name: str | None
    start_date: date | None
    end_date: date | None
    status: str
    gross_pay: Decimal | None
    net_pay: Decimal | None
    total_paid_hours: Decimal | None
    screenshot_hours: Decimal
    updated_at: datetime


class PayPeriodDetail(BaseModel):
    id: str
    employer_name: str | None
    start_date: date | None
    end_date: date | None
    status: str
    confirmed_at: datetime | None
    payslip: dict
    shifts: list[dict]
    screenshots: list[FileInfo]
    warnings: list[dict]
    reconciliation: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
