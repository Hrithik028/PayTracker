from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Correction,
    Employer,
    PayPeriod,
    Payslip,
    PayslipItem,
    Shift,
    ShiftPunch,
    ShiftScreenshot,
)
from app.schemas.pay_periods import PayPeriodCreate
from app.services.calculations import worked_hours
from app.services.reconciliation import reconcile
from app.services.validation import validate_period


LOAD_OPTIONS = (
    selectinload(PayPeriod.employer),
    selectinload(PayPeriod.payslip).selectinload(Payslip.items),
    selectinload(PayPeriod.payslip).selectinload(Payslip.extraction_results),
    selectinload(PayPeriod.screenshots).selectinload(
        ShiftScreenshot.extraction_results
    ),
    selectinload(PayPeriod.shifts).selectinload(Shift.punches),
)


def get_period(db: Session, period_id: str) -> PayPeriod | None:
    return db.scalar(
        select(PayPeriod).where(PayPeriod.id == period_id).options(*LOAD_OPTIONS)
    )


def list_periods(db: Session) -> list[PayPeriod]:
    return list(
        db.scalars(
            select(PayPeriod).options(*LOAD_OPTIONS).order_by(PayPeriod.updated_at.desc())
        ).all()
    )


def create_manual_period(
    db: Session, payload: PayPeriodCreate, *, commit: bool = True
) -> PayPeriod:
    period = PayPeriod(status="draft")
    db.add(period)
    db.flush()
    apply_payload(db, period, payload, audit=False)
    if commit:
        db.commit()
        return get_period(db, period.id)
    db.flush()
    return period


def apply_payload(
    db: Session, period: PayPeriod, payload: PayPeriodCreate, *, audit: bool = True
) -> PayPeriod:
    period.employer = _get_or_create_employer(db, payload.employer_name)
    _set_with_audit(db, period, "start_date", payload.start_date, period.id, audit)
    _set_with_audit(db, period, "end_date", payload.end_date, period.id, audit)

    if period.payslip is None:
        period.payslip = Payslip()
        db.flush()
    payslip = period.payslip
    for field in (
        "employee_name",
        "payment_date",
        "gross_pay",
        "net_pay",
        "tax_withheld",
        "superannuation",
        "total_paid_hours",
        "deductions",
        "allowances",
        "notes",
        "verified",
    ):
        _set_with_audit(
            db,
            payslip,
            field,
            getattr(payload.payslip, field),
            period.id,
            audit,
            "payslip",
        )

    existing_items = {item.id: item for item in payslip.items}
    retained_items: list[PayslipItem] = []
    for item_input in payload.payslip.items:
        item = existing_items.get(item_input.id) if item_input.id else None
        if item is None:
            item = PayslipItem(payslip=payslip)
            db.add(item)
            db.flush()
        for field in (
            "category",
            "description",
            "hours",
            "hourly_rate",
            "amount",
            "confidence_score",
            "source_text",
            "verified",
        ):
            _set_with_audit(
                db,
                item,
                field,
                getattr(item_input, field),
                period.id,
                audit,
                "payslip_item",
            )
        retained_items.append(item)
    retained_ids = {item.id for item in retained_items}
    for item in list(payslip.items):
        if item.id not in retained_ids:
            db.delete(item)

    existing_shifts = {shift.id: shift for shift in period.shifts}
    retained_shifts: list[Shift] = []
    for shift_input in payload.shifts:
        shift = existing_shifts.get(shift_input.id) if shift_input.id else None
        if shift is None:
            shift = Shift(pay_period=period)
            db.add(shift)
            db.flush()
        for field in (
            "source_screenshot_id",
            "shift_date",
            "start_time",
            "finish_time",
            "unpaid_break_minutes",
            "category",
            "confidence_score",
            "verified",
        ):
            _set_with_audit(
                db,
                shift,
                field,
                getattr(shift_input, field),
                period.id,
                audit,
                "shift",
            )
        calculated = worked_hours(
            shift_input.start_time,
            shift_input.finish_time,
            shift_input.unpaid_break_minutes,
        )
        _set_with_audit(
            db,
            shift,
            "total_worked_hours",
            calculated,
            period.id,
            audit,
            "shift",
        )
        existing_punches = {punch.id: punch for punch in shift.punches}
        # Move existing rows out of the final non-negative sequence range
        # before applying a reorder. Without this two-phase update, SQLite can
        # see a temporary duplicate when (for example) sequence 1 becomes 0
        # while the old sequence-0 row is still pending deletion.
        for temporary_sequence, punch in enumerate(existing_punches.values(), 1):
            punch.sequence = -temporary_sequence
        if existing_punches:
            db.flush()
        retained_punches: list[ShiftPunch] = []
        for sequence, punch_input in enumerate(shift_input.punches):
            punch = (
                existing_punches.get(punch_input.id)
                if punch_input.id
                else None
            )
            if punch is None:
                punch = ShiftPunch(
                    shift=shift,
                    sequence=-(len(existing_punches) + sequence + 1),
                )
                db.add(punch)
                db.flush()
            for field, value in (
                ("in_time", punch_input.in_time),
                ("out_time", punch_input.out_time),
                ("confidence_score", punch_input.confidence_score),
                ("verified", punch_input.verified),
            ):
                _set_with_audit(
                    db,
                    punch,
                    field,
                    value,
                    period.id,
                    audit,
                    "shift_punch",
                )
            retained_punches.append(punch)
        retained_punch_ids = {punch.id for punch in retained_punches}
        for punch in list(shift.punches):
            if punch.id not in retained_punch_ids:
                shift.punches.remove(punch)
        db.flush()
        for sequence, punch in enumerate(retained_punches):
            punch.sequence = sequence
        if retained_punches:
            db.flush()
        retained_shifts.append(shift)
    retained_shift_ids = {shift.id for shift in retained_shifts}
    for shift in list(period.shifts):
        if shift.id not in retained_shift_ids:
            db.delete(shift)
    period.updated_at = datetime.now(timezone.utc)
    db.flush()
    return period


def confirm_period(db: Session, period: PayPeriod) -> PayPeriod:
    period.status = "confirmed"
    period.confirmed_at = datetime.now(timezone.utc)
    if period.payslip:
        period.payslip.verified = True
        for item in period.payslip.items:
            item.verified = True
    for shift in period.shifts:
        shift.verified = True
        for punch in shift.punches:
            punch.verified = True
    db.commit()
    return get_period(db, period.id)


def serialize_period(period: PayPeriod) -> dict:
    payslip = period.payslip
    payslip_data = {
        "id": payslip.id if payslip else None,
        "original_filename": payslip.original_filename if payslip else None,
        "preview_url": f"/api/documents/payslip/{payslip.id}" if payslip and payslip.stored_path else None,
        "employee_name": payslip.employee_name if payslip else None,
        "payment_date": _iso(payslip.payment_date) if payslip else None,
        "gross_pay": _decimal(payslip.gross_pay) if payslip else None,
        "net_pay": _decimal(payslip.net_pay) if payslip else None,
        "tax_withheld": _decimal(payslip.tax_withheld) if payslip else None,
        "superannuation": _decimal(payslip.superannuation) if payslip else None,
        "total_paid_hours": _decimal(payslip.total_paid_hours) if payslip else None,
        "deductions": _decimal(payslip.deductions) if payslip else None,
        "allowances": _decimal(payslip.allowances) if payslip else None,
        "notes": payslip.notes if payslip else None,
        "field_confidence": payslip.field_confidence if payslip else {},
        "verified": payslip.verified if payslip else False,
        "items": [
            {
                "id": item.id,
                "category": item.category,
                "description": item.description,
                "hours": _decimal(item.hours),
                "hourly_rate": _decimal(item.hourly_rate),
                "amount": _decimal(item.amount),
                "confidence_score": item.confidence_score,
                "source_text": item.source_text,
                "verified": item.verified,
            }
            for item in (payslip.items if payslip else [])
        ],
    }
    shifts = [
        {
            "id": shift.id,
            "source_screenshot_id": shift.source_screenshot_id,
            "shift_date": _iso(shift.shift_date),
            "start_time": shift.start_time.strftime("%H:%M") if shift.start_time else None,
            "finish_time": shift.finish_time.strftime("%H:%M") if shift.finish_time else None,
            "unpaid_break_minutes": shift.unpaid_break_minutes,
            "total_worked_hours": _decimal(shift.total_worked_hours),
            "category": shift.category,
            "confidence_score": shift.confidence_score,
            "verified": shift.verified,
            "punches": [
                {
                    "id": punch.id,
                    "sequence": punch.sequence,
                    "in_time": punch.in_time.strftime("%H:%M")
                    if punch.in_time
                    else None,
                    "out_time": punch.out_time.strftime("%H:%M")
                    if punch.out_time
                    else None,
                    "confidence_score": punch.confidence_score,
                    "verified": punch.verified,
                }
                for punch in shift.punches
            ],
        }
        for shift in period.shifts
    ]
    warnings = validate_period(period)
    extraction_results = []
    if payslip:
        extraction_results.extend(payslip.extraction_results)
    for screenshot in period.screenshots:
        extraction_results.extend(screenshot.extraction_results)
    for result in extraction_results:
        warnings.extend(
            {
                "code": "extraction_warning",
                "message": message,
                "field": None,
                "state": "warning",
            }
            for message in result.warnings
        )
    return {
        "id": period.id,
        "employer_name": period.employer.name if period.employer else None,
        "start_date": _iso(period.start_date),
        "end_date": _iso(period.end_date),
        "status": period.status,
        "confirmed_at": _iso(period.confirmed_at),
        "payslip": payslip_data,
        "shifts": shifts,
        "screenshots": [
            {
                "id": screenshot.id,
                "original_filename": screenshot.original_filename,
                "preview_url": f"/api/documents/screenshot/{screenshot.id}",
            }
            for screenshot in period.screenshots
        ],
        "warnings": warnings,
        "reconciliation": reconcile(period),
        "created_at": _iso(period.created_at),
        "updated_at": _iso(period.updated_at),
    }


def serialize_summary(period: PayPeriod) -> dict:
    screenshot_hours = sum(
        (shift.total_worked_hours or Decimal("0") for shift in period.shifts),
        Decimal("0"),
    )
    return {
        "id": period.id,
        "employer_name": period.employer.name if period.employer else None,
        "start_date": _iso(period.start_date),
        "end_date": _iso(period.end_date),
        "status": period.status,
        "gross_pay": _decimal(period.payslip.gross_pay) if period.payslip else None,
        "net_pay": _decimal(period.payslip.net_pay) if period.payslip else None,
        "total_paid_hours": _decimal(period.payslip.total_paid_hours) if period.payslip else None,
        "screenshot_hours": _decimal(screenshot_hours),
        "updated_at": _iso(period.updated_at),
    }


def _get_or_create_employer(db: Session, name: str | None) -> Employer | None:
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    employer = db.scalar(select(Employer).where(Employer.name == cleaned))
    if employer:
        return employer
    employer = Employer(name=cleaned)
    db.add(employer)
    db.flush()
    return employer


def _set_with_audit(
    db: Session,
    entity,
    field: str,
    value,
    period_id: str,
    audit: bool,
    entity_type: str = "pay_period",
) -> None:
    previous = getattr(entity, field)
    if previous == value:
        return
    if audit and previous is not None:
        db.add(
            Correction(
                pay_period_id=period_id,
                entity_type=entity_type,
                entity_id=entity.id,
                field_name=field,
                extracted_value=str(previous),
                corrected_value=str(value) if value is not None else None,
                correction_time=datetime.now(timezone.utc),
            )
        )
    setattr(entity, field, value)


def _decimal(value) -> str | None:
    return str(value) if value is not None else None


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
