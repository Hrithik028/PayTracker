from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MONEY = Decimal("0.01")
HOURS = Decimal("0.01")


def worked_hours(
    start: time | None, finish: time | None, unpaid_break_minutes: int = 0
) -> Decimal | None:
    if start is None or finish is None:
        return None
    anchor = date(2000, 1, 1)
    start_dt = datetime.combine(anchor, start)
    finish_dt = datetime.combine(anchor, finish)
    if finish_dt <= start_dt:
        finish_dt += timedelta(days=1)
    minutes = Decimal(str((finish_dt - start_dt).total_seconds() / 60))
    minutes -= Decimal(unpaid_break_minutes)
    if minutes < 0:
        return Decimal("0.00")
    return (minutes / Decimal(60)).quantize(HOURS, rounding=ROUND_HALF_UP)


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def decimal_hours(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(HOURS, rounding=ROUND_HALF_UP)

