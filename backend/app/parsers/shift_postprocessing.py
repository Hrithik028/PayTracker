from __future__ import annotations

from collections import defaultdict
from datetime import datetime


QUARTER_HOUR_MINUTES = 15


def consolidate_daily_shifts(rows: list[dict]) -> tuple[list[dict], int, int]:
    """Combine punch pairs into one reviewed row per date.

    Clock-ins round forward to the next quarter hour and clock-outs round
    backward to the previous quarter hour, matching the attendance totals.
    Gaps between pairs become either a 60- or 120-minute unpaid break.
    """

    grouped: dict[str, list[dict]] = defaultdict(list)
    incomplete: list[dict] = []
    for row in rows:
        if row.get("shift_date") and row.get("start_time") and row.get("finish_time"):
            grouped[str(row["shift_date"])].append(row)
        else:
            incomplete.append(row)

    consolidated: list[dict] = []
    total_rounded_boundaries = 0
    total_normalized_breaks = 0
    for shift_date, day_rows in grouped.items():
        intervals: list[tuple[int, int, dict, int]] = []
        for row in day_rows:
            start = _minutes(str(row["start_time"]))
            finish = _minutes(str(row["finish_time"]))
            if start is None or finish is None:
                incomplete.append(row)
                continue

            adjusted_start, start_rounded = _round_start(start)
            adjusted_finish, finish_rounded = _round_finish(finish)
            original_finish = finish + (1440 if finish <= start else 0)
            normalized_finish = adjusted_finish + (
                1440 if adjusted_finish <= adjusted_start else 0
            )
            # Do not turn a short, valid shift crossing 4 PM into an overnight
            # shift when both boundaries round to the same time.
            if original_finish - start < 12 * 60 and normalized_finish - adjusted_start > 12 * 60:
                adjusted_start, adjusted_finish = start, finish
                start_rounded = finish_rounded = False
                normalized_finish = original_finish

            rounded = int(start_rounded) + int(finish_rounded)
            intervals.append((adjusted_start, normalized_finish, row, rounded))

        if not intervals:
            continue
        intervals.sort(key=lambda item: item[0])
        day_start = intervals[0][0]
        day_finish = intervals[0][1]
        unpaid_break = int(intervals[0][2].get("unpaid_break_minutes") or 0)
        rounded_boundaries = intervals[0][3]
        normalized_breaks = 0
        for start, finish, row, rounded in intervals[1:]:
            if start > day_finish:
                raw_gap = start - day_finish
                normalized_gap = _normalize_gap(raw_gap)
                unpaid_break += normalized_gap
                normalized_breaks += int(normalized_gap != raw_gap)
            day_finish = max(day_finish, finish)
            unpaid_break += int(row.get("unpaid_break_minutes") or 0)
            rounded_boundaries += rounded

        categories = {str(item[2].get("category") or "Ordinary") for item in intervals}
        category = next(iter(categories)) if len(categories) == 1 else "Other"
        confidence = min(int(item[2].get("confidence_score") or 0) for item in intervals)
        punches = [
            {
                "sequence": sequence,
                "in_time": str(item[2]["start_time"]),
                "out_time": str(item[2]["finish_time"]),
                "confidence_score": int(item[2].get("confidence_score") or 0),
                "verified": False,
            }
            for sequence, item in enumerate(intervals)
        ]
        total_rounded_boundaries += rounded_boundaries
        total_normalized_breaks += normalized_breaks
        consolidated.append(
            {
                "shift_date": shift_date,
                "start_time": _clock(day_start),
                "finish_time": _clock(day_finish),
                "unpaid_break_minutes": unpaid_break,
                "category": category,
                "confidence_score": confidence,
                "verified": False,
                "punches": punches,
                "source_text": (
                    f"Merged {len(intervals)} extracted punch pair(s); "
                    f"{rounded_boundaries} boundary time(s) rounded to a quarter hour; "
                    f"{normalized_breaks} gap(s) normalized to a whole-hour break."
                ),
            }
        )

    consolidated.sort(key=lambda row: (row.get("shift_date") or "", row.get("start_time") or ""))
    return consolidated + incomplete, total_rounded_boundaries, total_normalized_breaks


def _minutes(value: str) -> int | None:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def _clock(minutes: int) -> str:
    value = minutes % 1440
    return f"{value // 60:02d}:{value % 60:02d}"


def _round_start(minutes: int) -> tuple[int, bool]:
    rounded = (
        (minutes + QUARTER_HOUR_MINUTES - 1)
        // QUARTER_HOUR_MINUTES
        * QUARTER_HOUR_MINUTES
    )
    return rounded, rounded != minutes


def _round_finish(minutes: int) -> tuple[int, bool]:
    rounded = minutes // QUARTER_HOUR_MINUTES * QUARTER_HOUR_MINUTES
    return rounded, rounded != minutes


def _normalize_gap(minutes: int) -> int:
    """Attendance breaks are one or two whole hours, never odd minutes."""
    return 60 if minutes < 90 else 120
