from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDTimestampMixin


class Setting(UUIDTimestampMixin, Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Employer(UUIDTimestampMixin, Base):
    __tablename__ = "employers"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    pay_periods: Mapped[list["PayPeriod"]] = relationship(back_populates="employer")


class PayPeriod(UUIDTimestampMixin, Base):
    __tablename__ = "pay_periods"

    employer_id: Mapped[str | None] = mapped_column(
        ForeignKey("employers.id"), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employer: Mapped[Employer | None] = relationship(back_populates="pay_periods")
    payslip: Mapped["Payslip | None"] = relationship(
        back_populates="pay_period", cascade="all, delete-orphan", uselist=False
    )
    screenshots: Mapped[list["ShiftScreenshot"]] = relationship(
        back_populates="pay_period", cascade="all, delete-orphan"
    )
    shifts: Mapped[list["Shift"]] = relationship(
        back_populates="pay_period", cascade="all, delete-orphan"
    )
    exports: Mapped[list["Export"]] = relationship(
        back_populates="pay_period", cascade="all, delete-orphan"
    )
    corrections: Mapped[list["Correction"]] = relationship(
        back_populates="pay_period", cascade="all, delete-orphan"
    )


class Payslip(UUIDTimestampMixin, Base):
    __tablename__ = "payslips"

    pay_period_id: Mapped[str] = mapped_column(
        ForeignKey("pay_periods.id"), unique=True, nullable=False
    )
    original_filename: Mapped[str | None] = mapped_column(String(255))
    stored_path: Mapped[str | None] = mapped_column(String(500))
    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    employee_name: Mapped[str | None] = mapped_column(String(255))
    payment_date: Mapped[date | None] = mapped_column(Date)
    gross_pay: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    net_pay: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tax_withheld: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    superannuation: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_paid_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    deductions: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    allowances: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pay_period: Mapped[PayPeriod] = relationship(back_populates="payslip")
    items: Mapped[list["PayslipItem"]] = relationship(
        back_populates="payslip", cascade="all, delete-orphan"
    )
    extraction_results: Mapped[list["ExtractionResult"]] = relationship(
        back_populates="payslip", cascade="all, delete-orphan"
    )


class PayslipItem(UUIDTimestampMixin, Base):
    __tablename__ = "payslip_items"

    payslip_id: Mapped[str] = mapped_column(ForeignKey("payslips.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="Other", nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    payslip: Mapped[Payslip] = relationship(back_populates="items")


class ShiftScreenshot(UUIDTimestampMixin, Base):
    __tablename__ = "shift_screenshots"
    __table_args__ = (
        UniqueConstraint("file_hash", name="uq_shift_screenshot_file_hash"),
    )

    pay_period_id: Mapped[str] = mapped_column(
        ForeignKey("pay_periods.id"), nullable=False
    )
    original_filename: Mapped[str | None] = mapped_column(String(255))
    stored_path: Mapped[str | None] = mapped_column(String(500))
    file_hash: Mapped[str | None] = mapped_column(String(64))

    pay_period: Mapped[PayPeriod] = relationship(back_populates="screenshots")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="source_screenshot")
    extraction_results: Mapped[list["ExtractionResult"]] = relationship(
        back_populates="shift_screenshot", cascade="all, delete-orphan"
    )


class Shift(UUIDTimestampMixin, Base):
    __tablename__ = "shifts"

    pay_period_id: Mapped[str] = mapped_column(
        ForeignKey("pay_periods.id"), nullable=False
    )
    source_screenshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("shift_screenshots.id"), nullable=True
    )
    shift_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    finish_time: Mapped[time | None] = mapped_column(Time)
    unpaid_break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_worked_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(40), default="Ordinary", nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pay_period: Mapped[PayPeriod] = relationship(back_populates="shifts")
    source_screenshot: Mapped[ShiftScreenshot | None] = relationship(
        back_populates="shifts"
    )
    punches: Mapped[list["ShiftPunch"]] = relationship(
        back_populates="shift",
        cascade="all, delete-orphan",
        order_by="ShiftPunch.sequence",
    )


class ShiftPunch(UUIDTimestampMixin, Base):
    __tablename__ = "shift_punches"
    __table_args__ = (
        UniqueConstraint("shift_id", "sequence", name="uq_shift_punch_sequence"),
    )

    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    in_time: Mapped[time | None] = mapped_column(Time)
    out_time: Mapped[time | None] = mapped_column(Time)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    shift: Mapped[Shift] = relationship(back_populates="punches")


class ExtractionResult(UUIDTimestampMixin, Base):
    __tablename__ = "extraction_results"

    payslip_id: Mapped[str | None] = mapped_column(ForeignKey("payslips.id"))
    shift_screenshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("shift_screenshots.id")
    )
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structured_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    payslip: Mapped[Payslip | None] = relationship(back_populates="extraction_results")
    shift_screenshot: Mapped[ShiftScreenshot | None] = relationship(
        back_populates="extraction_results"
    )


class Correction(UUIDTimestampMixin, Base):
    __tablename__ = "corrections"

    pay_period_id: Mapped[str] = mapped_column(
        ForeignKey("pay_periods.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(Text)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    correction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pay_period: Mapped[PayPeriod] = relationship(back_populates="corrections")


class Export(UUIDTimestampMixin, Base):
    __tablename__ = "exports"

    pay_period_id: Mapped[str | None] = mapped_column(ForeignKey("pay_periods.id"))
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    pay_period: Mapped[PayPeriod | None] = relationship(back_populates="exports")
