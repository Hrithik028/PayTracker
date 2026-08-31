from datetime import date
from decimal import Decimal

from app.parsers.common import parse_currency, parse_date
from app.parsers.generic_payslip import GenericPayslipParser
from app.parsers.generic_shifts import GenericShiftParser
from app.parsers.coordinate_roster import CoordinateRosterParser
from app.parsers.shift_postprocessing import consolidate_daily_shifts


def test_currency_parser_handles_aud_format() -> None:
    assert parse_currency("$1,234.56") == Decimal("1234.56")


def test_date_parser_is_day_first() -> None:
    assert parse_date("1 July 2026").isoformat() == "2026-07-01"


def test_generic_payslip_parser_extracts_safe_synthetic_fields() -> None:
    text = """Example Retail Pty Ltd
Employer: Example Retail Pty Ltd
Employee: Sample Person
Pay Period: 01/07/2026 to 14/07/2026
Payment Date: 16/07/2026
Ordinary 20.00 30.0000 600.00
Gross Pay: $600.00
Tax Withheld: $100.00
Net Pay: $500.00
Total Paid Hours: 20.00
"""
    result = GenericPayslipParser().parse(text)
    assert result["employer_name"] == "Example Retail Pty Ltd"
    assert result["gross_pay"] == "600.00"
    assert result["pay_period_start"] == "2026-07-01"
    assert result["items"][0]["hours"] == "20.00"


def test_generic_shift_parser_extracts_time_range() -> None:
    rows = GenericShiftParser().parse("Wed 01/07/2026 9:00am - 5:30pm Break 30 min")
    assert len(rows) == 1
    assert rows[0]["start_time"] == "09:00"
    assert rows[0]["finish_time"] == "17:30"
    assert rows[0]["unpaid_break_minutes"] == 30


def test_weekly_block_shift_parser() -> None:
    text = """Weekly roster
01/07/2026 Wed 8:00
Work location 09:00
17:30
Second location 19:00
22:00
2 Thu 7:30
Work location 10:00
18:00
3 Fri 0:00
"""
    rows = GenericShiftParser().parse(text)
    assert len(rows) == 3
    assert rows[0]["shift_date"] == "2026-07-01"
    assert rows[0]["start_time"] == "09:00"
    assert rows[0]["finish_time"] == "17:30"
    assert rows[1]["start_time"] == "19:00"
    assert rows[1]["finish_time"] == "22:00"
    assert rows[2]["shift_date"] == "2026-07-02"


def test_coordinate_roster_assigns_punches_to_nearest_day_row() -> None:
    entries = [
        ("6/1", 70, 100, 94, 1),
        ("MON", 130, 100, 94, 1),
        ("2", 70, 220, 94, 2),
        ("TUE", 110, 220, 94, 2),
        ("10:56", 430, 300, 96, 3),
        ("14:17", 430, 360, 96, 4),
        ("3", 70, 420, 94, 5),
        ("WED", 110, 420, 94, 5),
        ("15:55", 430, 470, 96, 6),
        ("20:57", 430, 530, 96, 7),
        ("4", 70, 700, 94, 8),
        ("THU", 110, 700, 94, 8),
    ]
    data = {
        "text": [item[0] for item in entries],
        "left": [item[1] for item in entries],
        "top": [item[2] for item in entries],
        "width": [60] * len(entries),
        "height": [24] * len(entries),
        "conf": [item[3] for item in entries],
        "block_num": [1] * len(entries),
        "par_num": [1] * len(entries),
        "line_num": [item[4] for item in entries],
    }
    rows = CoordinateRosterParser().parse(data, 921, 900)
    assert len(rows) == 2
    assert rows[0]["shift_date"] == "2026-06-03"
    assert rows[0]["start_time"] == "10:56"
    assert rows[1]["shift_date"] == "2026-06-03"
    assert rows[1]["finish_time"] == "20:57"


def test_daily_punch_pairs_are_merged_with_whole_hour_break() -> None:
    rows, rounded, normalized_breaks = consolidate_daily_shifts(
        [
            {
                "shift_date": "2026-06-03",
                "start_time": "10:56",
                "finish_time": "14:17",
                "unpaid_break_minutes": 0,
                "category": "Ordinary",
                "confidence_score": 94,
            },
            {
                "shift_date": "2026-06-03",
                "start_time": "15:55",
                "finish_time": "20:57",
                "unpaid_break_minutes": 0,
                "category": "Ordinary",
                "confidence_score": 92,
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["start_time"] == "11:00"
    assert rows[0]["finish_time"] == "20:45"
    assert rows[0]["unpaid_break_minutes"] == 120
    assert rows[0]["confidence_score"] == 92
    assert rows[0]["punches"] == [
        {
            "sequence": 0,
            "in_time": "10:56",
            "out_time": "14:17",
            "confidence_score": 94,
            "verified": False,
        },
        {
            "sequence": 1,
            "in_time": "15:55",
            "out_time": "20:57",
            "confidence_score": 92,
            "verified": False,
        },
    ]
    assert rounded == 4
    assert normalized_breaks == 1


def test_clock_in_rounds_forward_and_clock_out_rounds_backward() -> None:
    rows, rounded, normalized_breaks = consolidate_daily_shifts(
        [
            {
                "shift_date": "2026-06-06",
                "start_time": "12:27",
                "finish_time": "16:08",
                "unpaid_break_minutes": 0,
                "category": "Saturday",
                "confidence_score": 94,
            }
        ]
    )
    assert rows[0]["start_time"] == "12:30"
    assert rows[0]["finish_time"] == "16:00"
    assert rounded == 2
    assert normalized_breaks == 0


def test_times_already_on_quarter_hour_are_not_changed() -> None:
    rows, rounded, normalized_breaks = consolidate_daily_shifts(
        [
            {
                "shift_date": "2026-06-04",
                "start_time": "15:30",
                "finish_time": "21:30",
                "unpaid_break_minutes": 0,
                "category": "Ordinary",
                "confidence_score": 84,
            }
        ]
    )
    assert rows[0]["start_time"] == "15:30"
    assert rounded == 0
    assert normalized_breaks == 0


def test_day_only_roster_dates_use_pay_period_context() -> None:
    entries = [
        ("17", 70, 200, 94, 1),
        ("WED", 110, 200, 94, 1),
        ("10:56", 430, 90, 96, 2),
        ("14:01", 430, 150, 96, 3),
        ("15:57", 430, 220, 96, 4),
        ("20:45", 430, 255, 96, 5),
    ]
    data = {
        "text": [item[0] for item in entries],
        "left": [item[1] for item in entries],
        "top": [item[2] for item in entries],
        "width": [60] * len(entries),
        "height": [24] * len(entries),
        "conf": [item[3] for item in entries],
        "block_num": [1] * len(entries),
        "par_num": [1] * len(entries),
        "line_num": [item[4] for item in entries],
    }
    rows = CoordinateRosterParser().parse(
        data,
        921,
        500,
        date(2026, 6, 15),
        date(2026, 6, 28),
    )
    assert len(rows) == 2
    assert {row["shift_date"] for row in rows} == {"2026-06-17"}


def test_column_layout_payslip_parser() -> None:
    text = """Example Retail Pty Ltd
Pay Period
1 July - 14 July 2026
Payment Date
16 July 2026
Pay Category
Rate
Units
This Pay
YTD
Ordinary
30.00
10.00
$300.00
$900.00
Saturday Rate
36.00
5.00
$180.00
$360.00
Gross
$480.00
$1,260.00
PAYG Tax
-$80.00
-$220.00
Net Pay
$400.00
$1,040.00
Superannuation
Rate
This Pay
YTD
Example Super
12 %
$57.60
$151.20
"""
    result = GenericPayslipParser().parse(text)
    assert result["pay_period_start"] == "2026-07-01"
    assert result["pay_period_end"] == "2026-07-14"
    assert result["payment_date"] == "2026-07-16"
    assert result["gross_pay"] == "480.00"
    assert result["net_pay"] == "400.00"
    assert result["tax_withheld"] == "80.00"
    assert result["superannuation"] == "57.60"
    assert result["total_paid_hours"] == "15.00"
    assert [item["category"] for item in result["items"]] == [
        "Ordinary",
        "Saturday",
    ]


def test_employee_name_above_employee_details_section() -> None:
    text = """Example Hospitality Pty Ltd
Sample Employee
10 Example Street
Exampletown NSW 2000
EMPLOYEE DETAILS
PAY DETAILS
Employee number
123
Employee type
Part time
Pay period
01 June - 14 June 2026
Gross
$500.00
Net Pay
$450.00
"""
    result = GenericPayslipParser().parse(text)
    assert result["employer_name"] == "Example Hospitality Pty Ltd"
    assert result["employee_name"] == "Sample Employee"
    assert result["confidence"]["employee_name"] == 72
