from datetime import date
from decimal import Decimal

from app.models import PayPeriod, Payslip, PayslipItem
from app.services.validation import validate_period


def test_payslip_arithmetic_warnings() -> None:
    period = PayPeriod(start_date=date(2026, 7, 1), end_date=date(2026, 7, 14))
    period.payslip = Payslip(
        gross_pay=Decimal("1000"),
        net_pay=Decimal("950"),
        tax_withheld=Decimal("200"),
        deductions=Decimal("0"),
    )
    period.payslip.items.append(
        PayslipItem(
            description="Ordinary",
            category="Ordinary",
            hours=Decimal("10"),
            hourly_rate=Decimal("30"),
            amount=Decimal("450"),
        )
    )
    codes = {item["code"] for item in validate_period(period)}
    assert "item_arithmetic" in codes
    assert "gross_mismatch" in codes
    assert "net_mismatch" in codes


def test_implausible_ocr_rate_is_warned() -> None:
    period = PayPeriod(start_date=date(2026, 7, 1), end_date=date(2026, 7, 14))
    period.payslip = Payslip()
    period.payslip.items.append(
        PayslipItem(
            description="Ordinary",
            category="Ordinary",
            hourly_rate=Decimal("3000"),
        )
    )
    assert "implausible_rate" in {item["code"] for item in validate_period(period)}

