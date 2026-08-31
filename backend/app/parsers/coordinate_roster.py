from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from app.parsers.common import parse_clock


WEEKDAYS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}
DATE_TOKEN = re.compile(r"^\d{1,2}(?:[./-]\d{1,2}(?:[./-]\d{2,4})?)?$")
TIME_TOKEN = re.compile(r"^\d{1,2}:\d{2}(?:am|pm)?$", re.IGNORECASE)


@dataclass(slots=True)
class OCRToken:
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    line_key: tuple[int, int, int]

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass(slots=True)
class DayAnchor:
    shift_date: date
    weekday_text: str
    center_y: float
    confidence: float


class CoordinateRosterParser:
    """Parse attendance screenshots using OCR token positions, not text order."""

    name = "coordinate-attendance-roster-v1"

    def parse(
        self,
        data: dict,
        image_width: int,
        image_height: int,
        pay_period_start: date | None = None,
        pay_period_end: date | None = None,
    ) -> list[dict]:
        tokens = self._tokens(data)
        anchors = self._anchors(tokens, pay_period_start, pay_period_end)
        if not anchors:
            return []

        punch_times = [
            token
            for token in tokens
            if TIME_TOKEN.match(token.text.replace(" ", ""))
            and image_width * 0.32 <= token.center_x <= image_width * 0.68
        ]
        punch_times.sort(key=lambda token: token.center_y)
        if len(punch_times) < 2:
            return []

        rows: list[dict] = []
        # The roster places a date label near the vertical centre of a day,
        # which means an early punch can sit above its date label. Pair punches
        # first and assign the complete pair by its centre instead of assigning
        # individual tokens with rigid row boundaries.
        for pair_index in range(0, len(punch_times) - 1, 2):
            start_token = punch_times[pair_index]
            finish_token = punch_times[pair_index + 1]
            pair_center_y = (start_token.center_y + finish_token.center_y) / 2
            anchor = min(
                anchors,
                key=lambda candidate: abs(candidate.center_y - pair_center_y),
            )
            start = parse_clock(start_token.text)
            finish = parse_clock(finish_token.text)
            if start is None or finish is None:
                continue
            confidence = round(
                min(
                    96,
                    max(
                        0,
                        (
                            anchor.confidence
                            + start_token.confidence
                            + finish_token.confidence
                        )
                        / 3,
                    ),
                )
            )
            rows.append(
                {
                    "shift_date": anchor.shift_date.isoformat(),
                    "start_time": start.strftime("%H:%M"),
                    "finish_time": finish.strftime("%H:%M"),
                    "unpaid_break_minutes": 0,
                    "category": self._category(anchor.shift_date),
                    "confidence_score": confidence,
                    "verified": False,
                    "source_text": "Coordinate-based attendance punch pair",
                }
            )
        return rows

    def _anchors(
        self,
        tokens: list[OCRToken],
        pay_period_start: date | None = None,
        pay_period_end: date | None = None,
    ) -> list[DayAnchor]:
        lines: dict[tuple[int, int, int], list[OCRToken]] = {}
        for token in tokens:
            lines.setdefault(token.line_key, []).append(token)

        candidates: list[tuple[OCRToken, OCRToken]] = []
        for line_tokens in lines.values():
            line_tokens.sort(key=lambda token: token.x)
            weekday = next(
                (
                    token
                    for token in line_tokens
                    if token.text.lower().strip(".,") in WEEKDAYS
                ),
                None,
            )
            if weekday is None:
                continue
            date_token = next(
                (
                    token
                    for token in line_tokens
                    if token.x < weekday.x
                    and DATE_TOKEN.match(token.text.strip())
                ),
                None,
            )
            if date_token:
                candidates.append((date_token, weekday))
        candidates.sort(key=lambda pair: pair[1].center_y)
        if not candidates:
            return []

        base: date | None = pay_period_start
        previous: date | None = None
        anchors: list[DayAnchor] = []
        for date_token, weekday_token in candidates:
            weekday_text = weekday_token.text.lower().strip(".,")
            expected_weekday = WEEKDAYS[weekday_text]
            value = date_token.text.strip()
            if re.search(r"[./-]", value):
                parsed = self._parse_ambiguous_date(value, expected_weekday)
                if parsed:
                    base = parsed
            else:
                parsed = self._date_from_day_number(
                    int(value), base, previous, expected_weekday
                )
            if parsed is None:
                continue
            if pay_period_start and parsed < pay_period_start:
                continue
            if pay_period_end and parsed > pay_period_end:
                continue
            previous = parsed
            anchors.append(
                DayAnchor(
                    shift_date=parsed,
                    weekday_text=weekday_text,
                    center_y=(date_token.center_y + weekday_token.center_y) / 2,
                    confidence=max(0, min(date_token.confidence, weekday_token.confidence)),
                )
            )
        return anchors

    @staticmethod
    def _tokens(data: dict) -> list[OCRToken]:
        tokens: list[OCRToken] = []
        for index, raw_text in enumerate(data.get("text", [])):
            text = str(raw_text).strip()
            if not text:
                continue
            try:
                confidence = float(data["conf"][index])
            except (KeyError, TypeError, ValueError):
                confidence = 0
            tokens.append(
                OCRToken(
                    text=text,
                    x=float(data["left"][index]),
                    y=float(data["top"][index]),
                    width=float(data["width"][index]),
                    height=float(data["height"][index]),
                    confidence=confidence,
                    line_key=(
                        int(data["block_num"][index]),
                        int(data["par_num"][index]),
                        int(data["line_num"][index]),
                    ),
                )
            )
        return tokens

    @staticmethod
    def _parse_ambiguous_date(value: str, expected_weekday: int) -> date | None:
        parts = [int(part) for part in re.split(r"[./-]", value)]
        if len(parts) not in {2, 3}:
            return None
        year = parts[2] if len(parts) == 3 else date.today().year
        if year < 100:
            year += 2000
        first, second = parts[0], parts[1]
        candidates: list[date] = []
        for month, day in ((first, second), (second, first)):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        matching = [
            candidate
            for candidate in candidates
            if candidate.weekday() == expected_weekday
        ]
        return matching[0] if matching else (candidates[0] if candidates else None)

    @staticmethod
    def _date_from_day_number(
        day: int,
        base: date | None,
        previous: date | None,
        expected_weekday: int,
    ) -> date | None:
        if base is None:
            return None
        year, month = base.year, base.month
        if previous and day < previous.day - 20:
            month += 1
            if month == 13:
                year, month = year + 1, 1
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate.weekday() == expected_weekday:
            return candidate
        # OCR may lose a digit. Search narrowly within the same month and trust
        # the visible weekday only when there is a unique nearby match.
        nearby = [
            date(year, month, possible_day)
            for possible_day in range(
                max(1, day - 2),
                min(calendar.monthrange(year, month)[1], day + 2) + 1,
            )
            if date(year, month, possible_day).weekday() == expected_weekday
        ]
        return nearby[0] if len(nearby) == 1 else candidate

    @staticmethod
    def _category(shift_date: date) -> str:
        if shift_date.weekday() == 5:
            return "Saturday"
        if shift_date.weekday() == 6:
            return "Sunday"
        return "Ordinary"
