from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from dateutil import parser as date_parser


MONEY_PATTERN = re.compile(r"-?\$?\s*[\d,]+(?:\.\d{1,4})?")
TIME_PATTERN = re.compile(
    r"\b(?P<start>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*"
    r"(?:-|–|—|to)\s*"
    r"(?P<finish>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
    re.IGNORECASE,
)


def parse_currency(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = MONEY_PATTERN.search(value.replace("O", "0"))
    if not match:
        return None
    cleaned = match.group(0).replace("$", "").replace(",", "").replace(" ", "")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", value.replace("O", "0"))
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", "."))
    except InvalidOperation:
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    try:
        return date_parser.parse(cleaned, dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def parse_clock(value: str) -> time | None:
    cleaned = value.strip().replace(".", ":").upper()
    formats = ("%I:%M%p", "%I%p", "%H:%M", "%H")
    cleaned = re.sub(r"\s+", "", cleaned)
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    return None


def parse_time_range(value: str) -> tuple[time | None, time | None]:
    match = TIME_PATTERN.search(value)
    if not match:
        return None, None
    return parse_clock(match.group("start")), parse_clock(match.group("finish"))


def confidence_for(text: str, label_found: bool, value_found: bool) -> int:
    if not value_found:
        return 0
    base = 82 if label_found else 58
    if len(text.strip()) < 3:
        base -= 15
    return max(0, min(100, base))

