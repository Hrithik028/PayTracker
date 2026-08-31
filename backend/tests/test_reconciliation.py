from datetime import date
from decimal import Decimal

from app.models import Employer, PayPeriod, Payslip, PayslipItem, Shift
from app.services.reconciliation import reconcile


def make_period(*, paid_hours: str, worked_hours: str, amount: str = "300") -> PayPeriod:
    period = PayPeriod(
        employer=Employer(name="Synthetic Employer"),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 14),
        status="needs_review",
    )
    period.payslip = Payslip(total_paid_hours=Decimal(paid_hours))
    period.payslip.items.append(
        PayslipItem(
            category="Ordinary",
            description="Ordinary hours",
            hours=Decimal("10"),
            hourly_rate=Decimal("30"),
            amount=Decimal(amount),
            verified=True,
        )
    )
    period.shifts.append(
        Shift(
            shift_date=date(2026, 7, 1),
            category="Ordinary",
            total_worked_hours=Decimal(worked_hours),
            verified=True,
        )
    )
    return period


def test_estimate_marks_paid_amount_above_category_estimate() -> None:
    result = reconcile(make_period(paid_hours="10", worked_hours="9"))

    assert result["estimated_pay_from_shifts"] == "270.00"
    assert result["paid_compared_earnings"] == "300.00"
    assert result["estimated_pay_difference"] == "30.00"
    assert result["estimated_pay_direction"] == "potentially_above"
    assert result["estimated_pay_complete"] is True


def test_estimate_marks_paid_amount_below_category_estimate() -> None:
    result = reconcile(make_period(paid_hours="10", worked_hours="11"))

    assert result["estimated_pay_from_shifts"] == "330.00"
    assert result["estimated_pay_difference"] == "-30.00"
    assert result["estimated_pay_direction"] == "potentially_below"
    assert result["estimated_pay_state"] == "discrepancy"


def test_estimate_stays_incomplete_without_matching_category_rate() -> None:
    period = make_period(paid_hours="10", worked_hours="9")
    period.shifts[0].category = "Sunday"

    result = reconcile(period)

    assert result["estimated_pay_direction"] == "unavailable"
    assert result["estimated_pay_complete"] is False
    assert result["category_pay_comparison"][0]["hourly_rate"] is None
