from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import AppSettings, get_settings
from app.database import get_db
from app.models import Export, Payslip, Setting, Shift, ShiftPunch, ShiftScreenshot
from app.schemas.pay_periods import PayPeriodCreate, PayPeriodUpdate
from app.security.files import (
    resolve_stored_file,
    store_validated_file,
    validate_upload,
)
from app.services.calculations import worked_hours
from app.services.excel_export import generate_workbook
from app.services.extraction import extract_payslip, extract_shifts
from app.services.pay_periods import (
    apply_payload,
    confirm_period,
    create_manual_period,
    get_period,
    list_periods,
    serialize_period,
    serialize_summary,
)
from app.services.validation import validate_period


router = APIRouter(prefix="/api")


class SettingsPayload(BaseModel):
    tesseract_cmd: str = ""
    currency: str = Field(default="AUD", max_length=8)
    time_format: str = Field(default="24h", pattern="^(12h|24h)$")
    backup_location: str = "backups"
    retain_uploads: bool = True
    max_upload_mb: int = Field(default=20, ge=1, le=100)

    @field_validator("backup_location")
    @classmethod
    def backup_must_be_local(cls, value: str) -> str:
        from app.config import project_path

        project_path(value)
        return value


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "application": "PayTracker",
        "storage": "local",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/settings")
def read_settings(
    db: Session = Depends(get_db),
    settings: AppSettings = Depends(get_settings),
) -> dict:
    values = {
        "tesseract_cmd": settings.tesseract_cmd,
        "currency": settings.currency,
        "time_format": settings.time_format,
        "backup_location": settings.backup_location,
        "retain_uploads": settings.retain_uploads,
        "max_upload_mb": settings.max_upload_mb,
    }
    for item in db.scalars(select(Setting)).all():
        if item.key in {"retain_uploads"}:
            values[item.key] = item.value.lower() == "true"
        elif item.key in {"max_upload_mb"}:
            values[item.key] = int(item.value)
        elif item.key in values:
            values[item.key] = item.value
    return values


@router.put("/settings")
def update_settings(payload: SettingsPayload, db: Session = Depends(get_db)) -> dict:
    for key, value in payload.model_dump().items():
        item = db.scalar(select(Setting).where(Setting.key == key))
        if item is None:
            item = Setting(key=key, value=str(value))
            db.add(item)
        else:
            item.value = str(value)
    db.commit()
    return payload.model_dump()


@router.get("/pay-periods")
def get_pay_periods(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_summary(period) for period in list_periods(db)]


@router.post("/pay-periods", status_code=201)
def post_pay_period(
    payload: PayPeriodCreate, db: Session = Depends(get_db)
) -> dict:
    return serialize_period(create_manual_period(db, payload))


@router.get("/pay-periods/{period_id}")
def get_pay_period(period_id: str, db: Session = Depends(get_db)) -> dict:
    period = get_period(db, period_id)
    if period is None:
        raise HTTPException(404, "Pay period not found")
    return serialize_period(period)


@router.put("/pay-periods/{period_id}")
def put_pay_period(
    period_id: str,
    payload: PayPeriodUpdate,
    db: Session = Depends(get_db),
) -> dict:
    period = get_period(db, period_id)
    if period is None:
        raise HTTPException(404, "Pay period not found")
    try:
        apply_payload(db, period, payload)
        if period.status == "confirmed":
            period.status = "needs_review"
            period.confirmed_at = None
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "The IN/OUT punch order could not be saved. Reload the shift table "
            "and try the edit again.",
        ) from exc
    return serialize_period(get_period(db, period_id))


@router.post("/pay-periods/{period_id}/confirm")
def post_confirm(
    period_id: str,
    db: Session = Depends(get_db),
    base_settings: AppSettings = Depends(get_settings),
) -> dict:
    period = get_period(db, period_id)
    if period is None:
        raise HTTPException(404, "Pay period not found")
    warnings = validate_period(period)
    blocking_codes = {"missing_dates", "invalid_date_range", "negative_value"}
    blockers = [item for item in warnings if item["code"] in blocking_codes]
    if blockers:
        raise HTTPException(
            422,
            {
                "message": "Resolve required validation warnings before confirmation.",
                "warnings": blockers,
            },
        )
    confirmed = confirm_period(db, period)
    if not _effective_settings(db, base_settings).retain_uploads:
        paths = _period_upload_paths(confirmed)
        if confirmed.payslip:
            confirmed.payslip.stored_path = None
        for screenshot in confirmed.screenshots:
            screenshot.stored_path = None
        db.commit()
        _remove_failed_uploads(paths)
        confirmed = get_period(db, period_id)
    return serialize_period(confirmed)


@router.delete("/pay-periods/{period_id}")
def delete_pay_period(period_id: str, db: Session = Depends(get_db)) -> dict:
    period = get_period(db, period_id)
    if period is None:
        raise HTTPException(404, "Pay period not found")
    paths = _period_upload_paths(period)
    db.delete(period)
    db.commit()
    _remove_failed_uploads(paths)
    return {"deleted": True}


@router.post("/process", status_code=201)
async def process_files(
    payslip_file: UploadFile = File(...),
    timing_files: list[UploadFile] = File(default=[]),
    employer_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    base_settings: AppSettings = Depends(get_settings),
) -> dict:
    payslip_validated = await validate_upload(payslip_file, base_settings)
    screenshot_validated = [
        await validate_upload(item, base_settings) for item in timing_files
    ]
    if db.scalar(select(Payslip.id).where(Payslip.file_hash == payslip_validated.sha256)):
        raise HTTPException(409, "This payslip has already been uploaded")
    hashes = [item.sha256 for item in screenshot_validated]
    if len(hashes) != len(set(hashes)):
        raise HTTPException(409, "The selected timing screenshots include duplicates")
    if hashes and db.scalar(
        select(ShiftScreenshot.id).where(ShiftScreenshot.file_hash.in_(hashes))
    ):
        raise HTTPException(409, "A selected timing screenshot was already uploaded")

    effective = _effective_settings(db, base_settings)
    payslip_path = store_validated_file(payslip_validated, "payslips")
    screenshot_paths = [
        store_validated_file(item, "timing-screenshots")
        for item in screenshot_validated
    ]
    try:
        extracted, raw_text, extraction_warnings = _safe_payslip_extraction(
            resolve_stored_file(payslip_path), effective
        )
        if not _has_usable_payslip_extraction(extracted):
            raise HTTPException(
                422,
                "The payslip did not produce usable financial data. "
                "No files or records were saved.",
            )
        payload = PayPeriodCreate(
            employer_name=employer_name or extracted.get("employer_name"),
            start_date=extracted.get("pay_period_start"),
            end_date=extracted.get("pay_period_end"),
            payslip={
                "employee_name": extracted.get("employee_name"),
                "payment_date": extracted.get("payment_date"),
                "gross_pay": extracted.get("gross_pay"),
                "net_pay": extracted.get("net_pay"),
                "tax_withheld": extracted.get("tax_withheld"),
                "superannuation": extracted.get("superannuation"),
                "total_paid_hours": extracted.get("total_paid_hours"),
                "deductions": extracted.get("deductions"),
                "allowances": extracted.get("allowances"),
                "notes": extracted.get("notes"),
                "items": extracted.get("items", []),
            },
        )
        period = create_manual_period(db, payload, commit=False)
        period.payslip.original_filename = payslip_validated.original_filename
        period.payslip.stored_path = payslip_path
        period.payslip.file_hash = payslip_validated.sha256
        period.payslip.field_confidence = extracted.get("confidence", {})
        from app.models import ExtractionResult

        period.payslip.extraction_results.append(
            ExtractionResult(
                parser_name="generic-payslip-v1",
                raw_text=raw_text,
                structured_data=extracted,
                warnings=extraction_warnings,
            )
        )

        for validated, stored_path in zip(screenshot_validated, screenshot_paths):
            rows, screenshot_text, screenshot_warnings = _safe_shift_extraction(
                resolve_stored_file(stored_path),
                effective,
                payload.start_date,
                payload.end_date,
            )
            if not _has_usable_shift_extraction(rows):
                date_hint = (
                    ""
                    if payload.start_date and payload.end_date
                    else " The screenshot must include a month and year when the "
                    "payslip pay-period dates cannot be extracted."
                )
                raise HTTPException(
                    422,
                    f"No complete shifts were extracted from "
                    f"{validated.original_filename}.{date_hint} "
                    "No files or records were saved.",
                )
            screenshot = ShiftScreenshot(
                pay_period=period,
                original_filename=validated.original_filename,
                stored_path=stored_path,
                file_hash=validated.sha256,
            )
            db.add(screenshot)
            db.flush()
            screenshot.extraction_results.append(
                ExtractionResult(
                    parser_name="generic-shifts-v1",
                    raw_text=screenshot_text,
                    structured_data={"shifts": rows},
                    warnings=screenshot_warnings,
                )
            )
            for row in rows:
                start_time = _parse_api_time(row.get("start_time"))
                finish_time = _parse_api_time(row.get("finish_time"))
                shift = Shift(
                    pay_period=period,
                    source_screenshot=screenshot,
                    shift_date=_parse_api_date(row.get("shift_date")),
                    start_time=start_time,
                    finish_time=finish_time,
                    unpaid_break_minutes=row.get("unpaid_break_minutes", 0),
                    total_worked_hours=worked_hours(
                        start_time,
                        finish_time,
                        row.get("unpaid_break_minutes", 0),
                    ),
                    category=row.get("category", "Ordinary"),
                    confidence_score=row.get("confidence_score", 0),
                )
                db.add(shift)
                db.flush()
                for sequence, punch in enumerate(row.get("punches", [])):
                    db.add(
                        ShiftPunch(
                            shift=shift,
                            sequence=sequence,
                            in_time=_parse_api_time(punch.get("in_time")),
                            out_time=_parse_api_time(punch.get("out_time")),
                            confidence_score=punch.get("confidence_score", 0),
                        )
                    )
        db.commit()
        return serialize_period(get_period(db, period.id))
    except HTTPException:
        db.rollback()
        _remove_failed_uploads([payslip_path, *screenshot_paths])
        raise
    except IntegrityError as exc:
        db.rollback()
        _remove_failed_uploads([payslip_path, *screenshot_paths])
        raise HTTPException(409, "One of these files has already been uploaded") from exc
    except Exception as exc:
        db.rollback()
        _remove_failed_uploads([payslip_path, *screenshot_paths])
        raise HTTPException(
            500,
            "Local processing could not create a review draft. No record was saved.",
        ) from exc


@router.get("/documents/{document_type}/{document_id}")
def preview_document(
    document_type: str, document_id: str, db: Session = Depends(get_db)
) -> FileResponse:
    if document_type == "payslip":
        document = db.get(Payslip, document_id)
    elif document_type == "screenshot":
        document = db.get(ShiftScreenshot, document_id)
    else:
        raise HTTPException(404, "Document not found")
    if document is None or not document.stored_path:
        raise HTTPException(404, "Document not found")
    path = resolve_stored_file(document.stored_path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/exports")
def export_records(
    period_id: str | None = None,
    db: Session = Depends(get_db),
    settings: AppSettings = Depends(get_settings),
) -> dict:
    periods = [period for period in list_periods(db) if period.status == "confirmed"]
    if period_id:
        periods = [period for period in periods if period.id == period_id]
    if not periods:
        raise HTTPException(422, "There are no confirmed records to export")
    path, relative = generate_workbook(periods, settings)
    export = Export(
        pay_period_id=period_id,
        stored_path=relative,
        exported_at=datetime.now(timezone.utc),
    )
    db.add(export)
    db.commit()
    return {
        "id": export.id,
        "filename": path.name,
        "download_url": f"/api/exports/{export.id}/download",
    }


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db)) -> FileResponse:
    export = db.get(Export, export_id)
    if export is None:
        raise HTTPException(404, "Export not found")
    path = (get_settings().exports_dir / Path(export.stored_path).name).resolve()
    try:
        path.relative_to(get_settings().exports_dir.resolve())
    except ValueError as exc:
        raise HTTPException(404, "Export not found") from exc
    if not path.is_file():
        raise HTTPException(404, "Export file not found")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    confirmed = [period for period in list_periods(db) if period.status == "confirmed"]
    totals = {
        "gross_pay": Decimal("0"),
        "net_pay": Decimal("0"),
        "tax_withheld": Decimal("0"),
        "superannuation": Decimal("0"),
        "confirmed_hours": Decimal("0"),
    }
    monthly: dict[str, Decimal] = {}
    unresolved = 0
    for period in confirmed:
        if period.payslip:
            totals["gross_pay"] += period.payslip.gross_pay or 0
            totals["net_pay"] += period.payslip.net_pay or 0
            totals["tax_withheld"] += period.payslip.tax_withheld or 0
            totals["superannuation"] += period.payslip.superannuation or 0
        totals["confirmed_hours"] += sum(
            (shift.total_worked_hours or 0 for shift in period.shifts), Decimal("0")
        )
        reference = period.end_date or period.start_date
        if reference and period.payslip:
            key = reference.strftime("%Y-%m")
            monthly[key] = monthly.get(key, Decimal("0")) + (period.payslip.gross_pay or 0)
        unresolved += sum(
            1
            for item in validate_period(period)
            if item["state"] in {"warning", "discrepancy"}
        )
    average = (
        totals["gross_pay"] / totals["confirmed_hours"]
        if totals["confirmed_hours"] > 0
        else Decimal("0")
    )
    return {
        "totals": {key: str(value.quantize(Decimal("0.01"))) for key, value in totals.items()},
        "effective_average_hourly_rate": str(average.quantize(Decimal("0.01"))),
        "unresolved_discrepancies": unresolved,
        "monthly_earnings": [
            {"month": key, "gross_pay": str(value.quantize(Decimal("0.01")))}
            for key, value in sorted(monthly.items())
        ],
        "recent_pay_periods": [serialize_summary(period) for period in list_periods(db)[:5]],
    }


def _effective_settings(db: Session, base: AppSettings) -> AppSettings:
    values = read_settings(db, base)
    return base.model_copy(update=values)


def _safe_payslip_extraction(path: Path, settings: AppSettings):
    try:
        return extract_payslip(path, settings)
    except Exception as exc:
        name = type(exc).__name__
        if name in {"TesseractNotFoundError", "TesseractError"}:
            return {}, "", ["Tesseract is unavailable. Enter the payslip details manually."]
        return {}, "", ["Local extraction could not process this file. Enter details manually."]


def _safe_shift_extraction(
    path: Path,
    settings: AppSettings,
    pay_period_start=None,
    pay_period_end=None,
):
    try:
        return extract_shifts(path, settings, pay_period_start, pay_period_end)
    except Exception as exc:
        name = type(exc).__name__
        if name in {"TesseractNotFoundError", "TesseractError"}:
            return [], "", ["Tesseract is unavailable. Add shifts manually."]
        return [], "", ["Local extraction could not process this image. Add shifts manually."]


def _has_usable_payslip_extraction(extracted: dict) -> bool:
    financial_fields = (
        "gross_pay",
        "net_pay",
        "tax_withheld",
        "superannuation",
        "total_paid_hours",
        "deductions",
        "allowances",
    )
    return bool(extracted.get("items")) or any(
        extracted.get(field) not in (None, "") for field in financial_fields
    )


def _has_usable_shift_extraction(rows: list[dict]) -> bool:
    return bool(rows) and all(
        row.get("shift_date") and row.get("start_time") and row.get("finish_time")
        for row in rows
    )


def _parse_api_time(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


def _parse_api_date(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _remove_failed_uploads(relative_paths: list[str]) -> None:
    for relative_path in relative_paths:
        try:
            resolve_stored_file(relative_path).unlink(missing_ok=True)
        except (OSError, HTTPException):
            # Never hide the original processing error because cleanup was blocked.
            continue


def _period_upload_paths(period) -> list[str]:
    paths: list[str] = []
    if period.payslip and period.payslip.stored_path:
        paths.append(period.payslip.stored_path)
    paths.extend(
        screenshot.stored_path
        for screenshot in period.screenshots
        if screenshot.stored_path
    )
    return paths
