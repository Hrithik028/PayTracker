from __future__ import annotations

from decimal import Decimal

from app.services.calculations import decimal_hours, money


def reconcile(period) -> dict:
    screenshot_hours = sum(
        (shift.total_worked_hours or Decimal("0") for shift in period.shifts),
        Decimal("0"),
    )
    paid_hours = (
        period.payslip.total_paid_hours
        if period.payslip and period.payslip.total_paid_hours is not None
        else Decimal("0")
    )
    hours_difference = decimal_hours(screenshot_hours - paid_hours)

    calculated_amount = Decimal("0")
    paid_amount = Decimal("0")
    if period.payslip:
        for item in period.payslip.items:
            if item.hours is not None and item.hourly_rate is not None:
                calculated_amount += item.hours * item.hourly_rate
            if item.amount is not None and item.category != "Deduction":
                paid_amount += item.amount
    amount_difference = money(calculated_amount - paid_amount)

    hours_state = "matching" if abs(hours_difference) <= Decimal("0.05") else (
        "warning" if abs(hours_difference) <= Decimal("0.25") else "discrepancy"
    )
    amount_state = "matching" if abs(amount_difference) <= Decimal("0.05") else (
        "warning" if abs(amount_difference) <= Decimal("1.00") else "discrepancy"
    )
    pay_estimate = _estimate_pay_from_shifts(period)
    return {
        "payslip_hours": str(decimal_hours(paid_hours)),
        "screenshot_hours": str(decimal_hours(screenshot_hours)),
        "hours_difference": str(hours_difference),
        "hours_state": hours_state,
        "calculated_amount": str(money(calculated_amount)),
        "paid_line_item_amount": str(money(paid_amount)),
        "amount_difference": str(amount_difference),
        "amount_state": amount_state,
        **pay_estimate,
        "label": "Potential discrepancy—review required"
        if "discrepancy"
        in {hours_state, amount_state, pay_estimate["estimated_pay_state"]}
        else "Review comparison",
    }


def _estimate_pay_from_shifts(period) -> dict:
    screenshot_hours: dict[str, Decimal] = {}
    for shift in period.shifts:
        category = shift.category or "Ordinary"
        screenshot_hours[category] = (
            screenshot_hours.get(category, Decimal("0"))
            + (shift.total_worked_hours or Decimal("0"))
        )

    pay_items: dict[str, dict[str, Decimal | bool]] = {}
    if period.payslip:
        for item in period.payslip.items:
            if (
                item.category == "Deduction"
                or item.hours is None
                or item.hours <= 0
                or item.hourly_rate is None
            ):
                continue
            values = pay_items.setdefault(
                item.category,
                {
                    "hours": Decimal("0"),
                    "rate_value": Decimal("0"),
                    "paid": Decimal("0"),
                    "amount_complete": True,
                },
            )
            values["hours"] += item.hours
            values["rate_value"] += item.hours * item.hourly_rate
            if item.amount is None:
                values["amount_complete"] = False
            else:
                values["paid"] += item.amount

    estimated_total = Decimal("0")
    paid_total = Decimal("0")
    complete = bool(screenshot_hours)
    category_rows: list[dict] = []
    for category in sorted(screenshot_hours):
        hours = screenshot_hours[category]
        item = pay_items.get(category)
        if not item or item["hours"] <= 0:
            complete = False
            category_rows.append(
                {
                    "category": category,
                    "screenshot_hours": str(decimal_hours(hours)),
                    "hourly_rate": None,
                    "estimated_pay": None,
                    "paid_amount": None,
                    "difference": None,
                }
            )
            continue
        rate = item["rate_value"] / item["hours"]
        estimated = hours * rate
        paid = item["paid"]
        if not item["amount_complete"]:
            complete = False
        estimated_total += estimated
        paid_total += paid
        category_rows.append(
            {
                "category": category,
                "screenshot_hours": str(decimal_hours(hours)),
                "hourly_rate": str(rate.quantize(Decimal("0.0001"))),
                "estimated_pay": str(money(estimated)),
                "paid_amount": str(money(paid)),
                "difference": str(money(paid - estimated)),
            }
        )

    unmatched_paid_categories = [
        category
        for category, values in pay_items.items()
        if values["hours"] > 0
        and category not in screenshot_hours
        and category not in {"Leave"}
    ]
    if unmatched_paid_categories:
        complete = False

    difference = money(paid_total - estimated_total)
    if (
        not complete
        or not category_rows
        or not any(row["hourly_rate"] for row in category_rows)
    ):
        direction = "unavailable"
        state = "warning"
        message = (
            "The estimate is incomplete because one or more worked categories "
            "do not have matching payslip rates and paid amounts."
        )
    elif difference > Decimal("1.00"):
        direction = "potentially_above"
        state = "warning"
        message = "Potentially paid above the calculated estimate."
    elif difference < Decimal("-1.00"):
        direction = "potentially_below"
        state = "discrepancy"
        message = "Potentially paid below the calculated estimate."
    else:
        direction = "approximately_matching"
        state = "matching"
        message = "Paid earnings approximately match the calculated estimate."

    return {
        "estimated_pay_from_shifts": str(money(estimated_total)),
        "paid_compared_earnings": str(money(paid_total)),
        "estimated_pay_difference": str(difference),
        "estimated_pay_direction": direction,
        "estimated_pay_state": state,
        "estimated_pay_complete": complete,
        "estimated_pay_message": message,
        "category_pay_comparison": category_rows,
    }
