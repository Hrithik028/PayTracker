from datetime import time
from decimal import Decimal

from app.services.calculations import money, worked_hours


def test_money_uses_decimal_rounding() -> None:
    assert money(Decimal("10.005")) == Decimal("10.01")


def test_worked_hours_deducts_break() -> None:
    assert worked_hours(time(9), time(17, 30), 30) == Decimal("8.00")


def test_worked_hours_supports_overnight_shift() -> None:
    assert worked_hours(time(22), time(6, 30), 30) == Decimal("8.00")


def test_worked_hours_never_negative() -> None:
    assert worked_hours(time(9), time(9, 30), 60) == Decimal("0.00")

