from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.services.calculations import money


def warning(code: str, message: str, field: str | None = None) -> dict:
    return {"code": code, "message": message, "field": field, "state": "warning"}


def validate_period(period) -> list[dict]:
    warnings: list[dict] = []
    payslip = period.payslip
    if not period.start_date or not period.end_date:
        warnings.append(warning("missing_dates", "Pay-period start and end dates are required."))
    elif period.end_date < period.start_date:
        warnings.append(
            warning("invalid_date_range", "End date is earlier than start date.", "end_date")
        )

    if payslip:
        numeric_fields = (
            "gross_pay",
            "net_pay",
            "tax_withheld",
            "superannuation",
            "total_paid_hours",
            "deductions",
            "allowances",
        )
        for field in numeric_fields:
            value = getattr(payslip, field)
            if value is not None and value < 0:
                warnings.append(warning("negative_value", f"{field.replace('_', ' ').title()} is negative.", field))

        earnings_total = Decimal("0")
        for item in payslip.items:
            if item.hours is not None and item.hourly_rate is not None and item.amount is not None:
                expected = money(item.hours * item.hourly_rate)
                if abs(expected - money(item.amount)) > Decimal("0.05"):
                    warnings.append(
                        warning(
                            "item_arithmetic",
                            f"{item.description or 'Pay item'}: hours × rate differs from amount.",
                            f"item:{item.id}",
                        )
                    )
            if item.hourly_rate is not None and item.hourly_rate > Decimal("1000"):
                warnings.append(
                    warning(
                        "implausible_rate",
                        f"{item.description or 'Pay item'} has an unusually large hourly rate; check for an OCR decimal error.",
                        f"item:{item.id}:hourly_rate",
                    )
                )
            if item.category not in {"Deduction"} and item.amount is not None:
                earnings_total += item.amount
            for field in ("hours", "hourly_rate", "amount"):
                value = getattr(item, field)
                if value is not None and value < 0 and item.category != "Deduction":
                    warnings.append(
                        warning("negative_value", f"{item.description or 'Pay item'} has a negative {field}.", f"item:{item.id}:{field}")
                    )

        if payslip.gross_pay is not None and earnings_total and abs(money(payslip.gross_pay) - money(earnings_total)) > Decimal("0.10"):
            warnings.append(
                warning("gross_mismatch", "Gross pay does not match the total of earnings line items.", "gross_pay")
            )
        if payslip.gross_pay is not None and payslip.net_pay is not None:
            approximate_net = money(
                payslip.gross_pay
                - (payslip.tax_withheld or 0)
                - (payslip.deductions or 0)
            )
            if abs(approximate_net - money(payslip.net_pay)) > Decimal("0.10"):
                warnings.append(
                    warning(
                        "net_mismatch",
                        "Net pay does not approximately match gross minus tax and deductions.",
                        "net_pay",
                    )
                )

    shifts = sorted(
        [shift for shift in period.shifts if shift.shift_date and shift.start_time],
        key=lambda item: (item.shift_date, item.start_time),
    )
    for shift in shifts:
        if shift.start_time == shift.finish_time:
            warnings.append(
                warning(
                    "equal_shift_times",
                    "A shift has equal start and finish times. Confirm whether this is an overnight 24-hour shift.",
                    f"shift:{shift.id}",
                )
            )
        if period.start_date and shift.shift_date and shift.shift_date < period.start_date:
            warnings.append(warning("shift_outside_period", "A shift falls before the pay period.", f"shift:{shift.id}"))
        if period.end_date and shift.shift_date and shift.shift_date > period.end_date:
            warnings.append(warning("shift_outside_period", "A shift falls after the pay period.", f"shift:{shift.id}"))

    for first, second in zip(shifts, shifts[1:]):
        first_start = datetime.combine(first.shift_date, first.start_time)
        first_finish = datetime.combine(first.shift_date, first.finish_time)
        if first_finish <= first_start:
            first_finish += timedelta(days=1)
        second_start = datetime.combine(second.shift_date, second.start_time)
        if second_start < first_finish:
            warnings.append(
                warning(
                    "overlapping_shifts",
                    "Two shifts overlap. Review their dates and times.",
                    f"shift:{second.id}",
                )
            )
    return warnings

