def payload():
    return {
        "employer_name": "Synthetic Café",
        "start_date": "2026-07-01",
        "end_date": "2026-07-14",
        "payslip": {
            "employee_name": "Sample Person",
            "payment_date": "2026-07-16",
            "gross_pay": "600.00",
            "net_pay": "500.00",
            "tax_withheld": "100.00",
            "superannuation": "72.00",
            "total_paid_hours": "20.00",
            "deductions": "0.00",
            "allowances": "0.00",
            "verified": False,
            "items": [
                {
                    "category": "Ordinary",
                    "description": "Ordinary hours",
                    "hours": "20.00",
                    "hourly_rate": "30.00",
                    "amount": "600.00",
                    "confidence_score": 100,
                    "verified": False,
                }
            ],
        },
        "shifts": [
            {
                "shift_date": "2026-07-01",
                "start_time": "09:00",
                "finish_time": "17:30",
                "unpaid_break_minutes": 30,
                "category": "Ordinary",
                "confidence_score": 100,
                "verified": False,
                "punches": [
                    {
                        "sequence": 0,
                        "in_time": "09:00",
                        "out_time": "17:30",
                        "confidence_score": 100,
                        "verified": False,
                    }
                ],
            }
        ],
    }


def test_manual_creation_edit_and_confirmation_flow(client) -> None:
    created = client.post("/api/pay-periods", json=payload())
    assert created.status_code == 201
    record = created.json()
    assert record["status"] == "draft"
    assert record["shifts"][0]["total_worked_hours"] == "8.00"
    assert record["shifts"][0]["punches"][0]["in_time"] == "09:00"

    edited_payload = payload()
    edited_payload["payslip"]["notes"] = "Reviewed against synthetic source"
    updated = client.put(f"/api/pay-periods/{record['id']}", json=edited_payload)
    assert updated.status_code == 200
    assert updated.json()["payslip"]["notes"] == "Reviewed against synthetic source"

    confirmed = client.post(f"/api/pay-periods/{record['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"]

    fetched = client.get(f"/api/pay-periods/{record['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["payslip"]["verified"] is True
    assert fetched.json()["shifts"][0]["punches"][0]["verified"] is True

    deleted = client.delete(f"/api/pay-periods/{record['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get(f"/api/pay-periods/{record['id']}").status_code == 404


def test_confirmation_requires_dates(client) -> None:
    body = payload()
    body["start_date"] = None
    body["end_date"] = None
    record = client.post("/api/pay-periods", json=body).json()
    response = client.post(f"/api/pay-periods/{record['id']}/confirm")
    assert response.status_code == 422


def test_removing_first_punch_resequences_remaining_pair(client) -> None:
    body = payload()
    body["shifts"][0].update(
        {
            "start_time": "09:00",
            "finish_time": "19:00",
            "unpaid_break_minutes": 60,
            "punches": [
                {
                    "sequence": 0,
                    "in_time": "09:00",
                    "out_time": "12:00",
                    "confidence_score": 90,
                    "verified": False,
                },
                {
                    "sequence": 1,
                    "in_time": "13:00",
                    "out_time": "19:00",
                    "confidence_score": 90,
                    "verified": False,
                },
            ],
        }
    )
    created = client.post("/api/pay-periods", json=body)
    assert created.status_code == 201
    record = created.json()
    remaining = record["shifts"][0]["punches"][1]

    edited = payload()
    edited["shifts"][0].update(
        {
            "id": record["shifts"][0]["id"],
            "start_time": "13:00",
            "finish_time": "19:00",
            "unpaid_break_minutes": 0,
            "punches": [
                {
                    **remaining,
                    "sequence": 0,
                }
            ],
        }
    )
    updated = client.put(f"/api/pay-periods/{record['id']}", json=edited)

    assert updated.status_code == 200
    punches = updated.json()["shifts"][0]["punches"]
    assert len(punches) == 1
    assert punches[0]["id"] == remaining["id"]
    assert punches[0]["sequence"] == 0
