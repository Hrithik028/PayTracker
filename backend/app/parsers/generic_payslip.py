from __future__ import annotations

import re
from decimal import Decimal

from app.parsers.common import confidence_for, parse_currency, parse_date, parse_decimal


class GenericPayslipParser:
    """Conservative, layout-independent rules. Unknown values remain blank."""

    name = "generic-payslip-v1"

    LABELS = {
        "gross_pay": r"(?:gross\s*(?:pay|earnings|total))",
        "net_pay": r"(?:net\s*(?:pay|amount)|take\s*home)",
        "tax_withheld": r"(?:tax\s*(?:withheld|deducted)?|PAYG)",
        "superannuation": r"(?:super(?:annuation)?(?:\s*contribution)?)",
        "total_paid_hours": r"(?:total\s*(?:paid\s*)?hours)",
        "deductions": r"(?:total\s*deductions?)",
        "allowances": r"(?:total\s*allowances?)",
    }

    def parse(self, text: str) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        result: dict = {
            "employer_name": None,
            "employee_name": None,
            "pay_period_start": None,
            "pay_period_end": None,
            "payment_date": None,
            "gross_pay": None,
            "net_pay": None,
            "tax_withheld": None,
            "superannuation": None,
            "total_paid_hours": None,
            "deductions": None,
            "allowances": None,
            "notes": None,
            "items": [],
            "confidence": {},
        }

        for line in lines:
            for field, label in self.LABELS.items():
                match = re.search(
                    rf"{label}\s*[:\-]?\s*(\$?\s*[\d,]+(?:\.\d{{1,4}})?)",
                    line,
                    re.IGNORECASE,
                )
                if match and result[field] is None:
                    value = (
                        parse_decimal(match.group(1))
                        if field == "total_paid_hours"
                        else parse_currency(match.group(1))
                    )
                    result[field] = str(value) if value is not None else None
                    result["confidence"][field] = confidence_for(line, True, value is not None)

            pay_period = re.search(
                r"pay\s*period\s*[:\-]?\s*(.+?)\s+(?:to|-|–)\s+(.+)$",
                line,
                re.IGNORECASE,
            )
            if pay_period and result["pay_period_start"] is None:
                start = parse_date(pay_period.group(1))
                end = parse_date(pay_period.group(2))
                result["pay_period_start"] = start.isoformat() if start else None
                result["pay_period_end"] = end.isoformat() if end else None
                result["confidence"]["pay_period_start"] = confidence_for(
                    line, True, start is not None
                )
                result["confidence"]["pay_period_end"] = confidence_for(
                    line, True, end is not None
                )

            payment = re.search(
                r"(?:payment|pay)\s*date\s*[:\-]?\s*(.+)$", line, re.IGNORECASE
            )
            if payment and result["payment_date"] is None:
                value = parse_date(payment.group(1))
                result["payment_date"] = value.isoformat() if value else None
                result["confidence"]["payment_date"] = confidence_for(
                    line, True, value is not None
                )

            employee = re.search(
                r"employee(?:\s*name)?\s*[:\-]\s*(.+)$", line, re.IGNORECASE
            )
            if employee and result["employee_name"] is None:
                result["employee_name"] = employee.group(1).strip()
                result["confidence"]["employee_name"] = 78

            employer = re.search(
                r"employer(?:\s*name)?\s*[:\-]\s*(.+)$", line, re.IGNORECASE
            )
            if employer and result["employer_name"] is None:
                result["employer_name"] = employer.group(1).strip()
                result["confidence"]["employer_name"] = 78

            item = self._parse_line_item(line)
            if item:
                result["items"].append(item)

        self._parse_sequential_fields(lines, result)
        self._parse_header_employee(lines, result)
        if not result["items"]:
            result["items"] = self._parse_column_items(lines)
        if result["total_paid_hours"] is None and result["items"]:
            hours = sum(
                (
                    Decimal(item["hours"])
                    for item in result["items"]
                    if item.get("hours") is not None
                    and item.get("category") != "Leave"
                ),
                Decimal("0"),
            )
            if hours:
                result["total_paid_hours"] = str(hours.quantize(Decimal("0.01")))
                result["confidence"]["total_paid_hours"] = 68

        if not result["employer_name"] and lines:
            first = lines[0]
            if len(first) <= 100 and not any(char.isdigit() for char in first):
                result["employer_name"] = first
                result["confidence"]["employer_name"] = 45
        return result

    @staticmethod
    def _parse_header_employee(lines: list[str], result: dict) -> None:
        """Find an employee name printed above an EMPLOYEE DETAILS section."""
        if result["employee_name"] is not None:
            return
        section_index = next(
            (
                index
                for index, line in enumerate(lines)
                if re.fullmatch(r"employee\s+details", line, re.IGNORECASE)
            ),
            None,
        )
        if section_index is None:
            return

        business_words = re.compile(
            r"\b(?:abn|pty|ltd|limited|company|corporation|corp|group|"
            r"trading|holdings|inc|llc)\b",
            re.IGNORECASE,
        )
        for candidate in reversed(lines[max(0, section_index - 8) : section_index]):
            value = candidate.strip()
            words = value.split()
            if (
                not 2 <= len(words) <= 6
                or len(value) > 100
                or any(char.isdigit() for char in value)
                or "@" in value
                or business_words.search(value)
                or not all(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+", word) for word in words)
            ):
                continue
            result["employee_name"] = value
            result["confidence"]["employee_name"] = 72
            return

    def _parse_sequential_fields(self, lines: list[str], result: dict) -> None:
        """Parse PDFs whose visual columns are emitted as consecutive lines."""
        lowered = [line.lower().strip() for line in lines]
        money_labels = {
            "gross_pay": re.compile(r"^gross(?:\s+(?:pay|earnings))?$", re.I),
            "net_pay": re.compile(r"^net\s+pay$", re.I),
            "tax_withheld": re.compile(r"^(?:payg\s+)?tax(?:\s+withheld)?$", re.I),
            "deductions": re.compile(r"^(?:total\s+)?deductions?$", re.I),
            "allowances": re.compile(r"^(?:total\s+)?allowances?$", re.I),
        }
        for field, pattern in money_labels.items():
            if result[field] is not None:
                continue
            for index, line in enumerate(lines):
                if not pattern.search(line.strip()):
                    continue
                value = self._first_money(lines, index + 1, index + 4)
                if value is not None:
                    if field in {"tax_withheld", "deductions"}:
                        value = abs(value)
                    result[field] = str(value)
                    result["confidence"][field] = 86
                    break

        if result["pay_period_start"] is None:
            for index, line in enumerate(lowered):
                if line != "pay period":
                    continue
                for candidate in lines[index + 1 : index + 4]:
                    match = re.search(r"(.+?)\s+(?:-|–|—|to)\s+(.+)", candidate, re.I)
                    if not match:
                        continue
                    end = parse_date(match.group(2))
                    if not end:
                        continue
                    start_text = match.group(1)
                    if not re.search(r"\b\d{4}\b", start_text):
                        start_text = f"{start_text} {end.year}"
                    start = parse_date(start_text)
                    if start and start > end:
                        start = start.replace(year=end.year - 1)
                    if start:
                        result["pay_period_start"] = start.isoformat()
                        result["pay_period_end"] = end.isoformat()
                        result["confidence"]["pay_period_start"] = 86
                        result["confidence"]["pay_period_end"] = 86
                        break
                if result["pay_period_start"]:
                    break

        if result["payment_date"] is None:
            for index, line in enumerate(lowered):
                if line != "payment date":
                    continue
                for candidate in lines[index + 1 : index + 4]:
                    value = parse_date(candidate)
                    if value:
                        result["payment_date"] = value.isoformat()
                        result["confidence"]["payment_date"] = 86
                        break
                if result["payment_date"]:
                    break

        if result["superannuation"] is None:
            for index, line in enumerate(lowered):
                if line != "superannuation":
                    continue
                percentage_index = next(
                    (
                        offset
                        for offset in range(index + 1, min(index + 12, len(lines)))
                        if "%" in lines[offset]
                    ),
                    None,
                )
                if percentage_index is not None:
                    value = self._first_money(
                        lines, percentage_index + 1, percentage_index + 5
                    )
                    if value is not None:
                        result["superannuation"] = str(abs(value))
                        result["confidence"]["superannuation"] = 76
                break

    def _parse_column_items(self, lines: list[str]) -> list[dict]:
        items: list[dict] = []
        category_patterns = (
            (re.compile(r"^ordinary\b", re.I), "Ordinary"),
            (re.compile(r"^overtime\b", re.I), "Overtime"),
            (re.compile(r"^saturday\b", re.I), "Saturday"),
            (re.compile(r"^sunday\b", re.I), "Sunday"),
            (re.compile(r"^public\s+holiday\b", re.I), "Public holiday"),
        )
        for index, line in enumerate(lines):
            category = next(
                (name for pattern, name in category_patterns if pattern.search(line)),
                None,
            )
            if not category:
                continue
            following = lines[index + 1 : index + 6]
            plain_numbers: list[Decimal] = []
            amount: Decimal | None = None
            source_lines = [line]
            for candidate in following:
                if self._looks_like_section_label(candidate):
                    break
                source_lines.append(candidate)
                if "$" in candidate and amount is None:
                    amount = parse_currency(candidate)
                elif "$" not in candidate:
                    value = parse_decimal(candidate)
                    if value is not None:
                        plain_numbers.append(value)
                if amount is not None and len(plain_numbers) >= 2:
                    break
            if len(plain_numbers) < 2 or amount is None:
                continue
            rate, hours = plain_numbers[0], plain_numbers[1]
            items.append(
                {
                    "category": category,
                    "description": line.strip(),
                    "hours": str(hours),
                    "hourly_rate": str(rate),
                    "amount": str(amount),
                    "confidence_score": 78,
                    "source_text": "\n".join(source_lines),
                    "verified": False,
                }
            )
        return items

    @staticmethod
    def _first_money(
        lines: list[str], start: int, stop: int
    ) -> Decimal | None:
        for candidate in lines[start : min(stop, len(lines))]:
            if "$" not in candidate:
                continue
            value = parse_currency(candidate)
            if value is not None:
                return value
        return None

    @staticmethod
    def _looks_like_section_label(line: str) -> bool:
        return bool(
            re.search(
                r"^(?:ordinary|overtime|saturday|sunday|public\s+holiday|"
                r"annual\s+leave|gross|net\s+pay|(?:payg\s+)?tax|superannuation)$",
                line.strip(),
                re.I,
            )
        )

    def _parse_line_item(self, line: str) -> dict | None:
        match = re.search(
            r"^(?P<description>[A-Za-z][A-Za-z /&()\-]+?)\s+"
            r"(?P<hours>\d+(?:\.\d+)?)\s+"
            r"(?P<rate>\d+(?:\.\d{1,4})?)\s+"
            r"\$?(?P<amount>[\d,]+(?:\.\d{2}))$",
            line,
        )
        if not match:
            return None
        description = match.group("description").strip()
        category = self._category(description)
        return {
            "category": category,
            "description": description,
            "hours": str(Decimal(match.group("hours"))),
            "hourly_rate": str(Decimal(match.group("rate"))),
            "amount": str(parse_currency(match.group("amount"))),
            "confidence_score": 70,
            "source_text": line,
            "verified": False,
        }

    @staticmethod
    def _category(description: str) -> str:
        lowered = description.lower()
        for key, category in (
            ("public", "Public holiday"),
            ("sunday", "Sunday"),
            ("saturday", "Saturday"),
            ("overtime", "Overtime"),
            ("leave", "Leave"),
            ("allowance", "Allowance"),
            ("bonus", "Bonus"),
            ("deduction", "Deduction"),
            ("ordinary", "Ordinary"),
        ):
            if key in lowered:
                return category
        return "Other"
