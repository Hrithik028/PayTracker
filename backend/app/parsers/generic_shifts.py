from __future__ import annotations

import calendar
import re
from datetime import date

from app.parsers.common import parse_clock, parse_date, parse_time_range


class GenericShiftParser:
    name = "generic-shifts-v1"
    DAY_ANCHOR = re.compile(
        r"(?:(?P<date>\d{1,2}(?:[./-]\d{1,2}(?:[./-]\d{2,4})?)?)\s+)?"
        r"(?P<day>mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|"
        r"thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
        re.IGNORECASE,
    )
    CLOCK = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", re.IGNORECASE)

    def parse(self, text: str) -> list[dict]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        shifts: list[dict] = []
        for line in lines:
            start, finish = parse_time_range(line)
            if not start or not finish:
                continue
            date_match = re.search(
                r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?[a-z]*\s*"
                r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
                r"\d{1,2}\s+[A-Za-z]{3,9}(?:\s+\d{2,4})?)",
                line,
                re.IGNORECASE,
            )
            shift_date = parse_date(date_match.group(1)) if date_match else None
            break_match = re.search(
                r"(?:break|unpaid)\s*[:\-]?\s*(\d{1,3})\s*(?:m|min)?",
                line,
                re.IGNORECASE,
            )
            shifts.append(
                {
                    "shift_date": shift_date.isoformat() if shift_date else None,
                    "start_time": start.strftime("%H:%M"),
                    "finish_time": finish.strftime("%H:%M"),
                    "unpaid_break_minutes": int(break_match.group(1))
                    if break_match
                    else 0,
                    "category": self._category(line),
                    "confidence_score": 76 if shift_date else 58,
                    "verified": False,
                    "source_text": line,
                }
            )
        return shifts or self._parse_weekly_blocks(lines)

    def _parse_weekly_blocks(self, lines: list[str]) -> list[dict]:
        """Parse roster screenshots that split each day and its times over lines."""
        anchors: list[tuple[int, re.Match[str]]] = []
        for index, line in enumerate(lines):
            match = self.DAY_ANCHOR.search(line)
            if match:
                anchors.append((index, match))
        if not anchors:
            return []

        base_date = self._first_full_date(anchors)
        previous_date: date | None = None
        shifts: list[dict] = []
        for anchor_index, (line_index, match) in enumerate(anchors):
            next_index = (
                anchors[anchor_index + 1][0]
                if anchor_index + 1 < len(anchors)
                else len(lines)
            )
            shift_date = self._date_for_anchor(
                match.group("date"), base_date, previous_date
            )
            if shift_date:
                previous_date = shift_date

            # The time printed on a weekday heading is commonly the daily total.
            # Only pair clocks from the detail lines beneath that heading.
            detail_lines = lines[line_index + 1 : next_index]
            clocks = [
                parsed
                for detail in detail_lines
                for token in self.CLOCK.findall(detail)
                if (parsed := parse_clock(token)) is not None
            ]
            break_match = re.search(
                r"(?:break|unpaid)\s*[:\-]?\s*(\d{1,3})\s*(?:m|min)?",
                "\n".join(detail_lines),
                re.IGNORECASE,
            )
            break_minutes = int(break_match.group(1)) if break_match else 0
            for pair_index in range(0, len(clocks) - 1, 2):
                start, finish = clocks[pair_index], clocks[pair_index + 1]
                shifts.append(
                    {
                        "shift_date": shift_date.isoformat() if shift_date else None,
                        "start_time": start.strftime("%H:%M"),
                        "finish_time": finish.strftime("%H:%M"),
                        "unpaid_break_minutes": break_minutes,
                        "category": self._category(match.group("day")),
                        "confidence_score": 62,
                        "verified": False,
                        "source_text": "\n".join(
                            [lines[line_index], *detail_lines]
                        ),
                    }
                )
        return shifts

    def _first_full_date(
        self, anchors: list[tuple[int, re.Match[str]]]
    ) -> date | None:
        for _, match in anchors:
            value = match.group("date")
            if value and re.search(r"[./-]", value):
                parsed = parse_date(value)
                if parsed:
                    return parsed
        return None

    @staticmethod
    def _date_for_anchor(
        value: str | None, base: date | None, previous: date | None
    ) -> date | None:
        if value and re.search(r"[./-]", value):
            return parse_date(value)
        if not value or not value.isdigit() or base is None:
            return None
        day = int(value)
        year, month = base.year, base.month
        if previous and day < previous.day - 20:
            month += 1
            if month == 13:
                month = 1
                year += 1
        day = min(day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _category(line: str) -> str:
        lowered = line.lower()
        if "public holiday" in lowered:
            return "Public holiday"
        if "sunday" in lowered or lowered.startswith("sun"):
            return "Sunday"
        if "saturday" in lowered or lowered.startswith("sat"):
            return "Saturday"
        return "Ordinary"
