from __future__ import annotations

import importlib
import io
from pathlib import Path

from PIL import Image


router_module = importlib.import_module("app.api.router")


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (80, 80), "white").save(output, format="PNG")
    return output.getvalue()


def _temporary_storage(monkeypatch, tmp_path: Path) -> list[Path]:
    stored: dict[str, Path] = {}
    created: list[Path] = []

    def store(file, subdirectory: str) -> str:
        key = f"{subdirectory}-{len(created)}{file.extension}"
        path = tmp_path / key
        path.write_bytes(file.content)
        stored[key] = path
        created.append(path)
        return key

    monkeypatch.setattr(router_module, "store_validated_file", store)
    monkeypatch.setattr(
        router_module,
        "resolve_stored_file",
        lambda relative_path: stored[relative_path],
    )
    return created


def _mock_successful_payslip(monkeypatch) -> None:
    monkeypatch.setattr(
        router_module,
        "_safe_payslip_extraction",
        lambda _path, _settings: (
            {
                "pay_period_start": "2026-06-01",
                "pay_period_end": "2026-06-14",
                "gross_pay": "100.00",
                "net_pay": "100.00",
                "tax_withheld": "0.00",
                "total_paid_hours": "1.00",
                "items": [
                    {
                        "category": "Ordinary",
                        "description": "Synthetic ordinary hours",
                        "hours": "1.00",
                        "hourly_rate": "100.00",
                        "amount": "100.00",
                        "confidence_score": 100,
                        "verified": False,
                    }
                ],
            },
            "synthetic text",
            [],
        ),
    )


def test_failed_payslip_extraction_removes_file_and_record(
    client, monkeypatch, tmp_path: Path
) -> None:
    created = _temporary_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        router_module,
        "_safe_payslip_extraction",
        lambda _path, _settings: ({}, "", ["No usable data"]),
    )

    response = client.post(
        "/api/process",
        files={"payslip_file": ("synthetic.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 422
    assert "No files or records were saved" in response.json()["detail"]
    assert created and all(not path.exists() for path in created)
    assert client.get("/api/pay-periods").json() == []


def test_failed_screenshot_extraction_removes_all_files_and_record(
    client, monkeypatch, tmp_path: Path
) -> None:
    created = _temporary_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        router_module,
        "_safe_payslip_extraction",
        lambda _path, _settings: (
            {"gross_pay": "100.00", "items": []},
            "synthetic text",
            [],
        ),
    )
    monkeypatch.setattr(
        router_module,
        "_safe_shift_extraction",
        lambda _path, _settings, *_period: ([], "", ["No complete shifts"]),
    )

    image = _png_bytes()
    response = client.post(
        "/api/process",
        files=[
            ("payslip_file", ("payslip.png", image, "image/png")),
            ("timing_files", ("timetable.png", image, "image/png")),
        ],
    )

    assert response.status_code == 422
    assert "No files or records were saved" in response.json()["detail"]
    assert len(created) == 2
    assert all(not path.exists() for path in created)
    assert client.get("/api/pay-periods").json() == []


def test_deleting_draft_removes_generated_upload_copy(
    client, monkeypatch, tmp_path: Path
) -> None:
    created = _temporary_storage(monkeypatch, tmp_path)
    _mock_successful_payslip(monkeypatch)
    processed = client.post(
        "/api/process",
        files={"payslip_file": ("synthetic.png", _png_bytes(), "image/png")},
    )
    assert processed.status_code == 201
    assert created[0].exists()

    deleted = client.delete(f"/api/pay-periods/{processed.json()['id']}")

    assert deleted.status_code == 200
    assert not created[0].exists()


def test_disabled_retention_removes_copy_after_confirmation(
    client, monkeypatch, tmp_path: Path
) -> None:
    created = _temporary_storage(monkeypatch, tmp_path)
    _mock_successful_payslip(monkeypatch)
    settings = {
        "tesseract_cmd": "",
        "currency": "AUD",
        "time_format": "24h",
        "backup_location": "backups",
        "retain_uploads": False,
        "max_upload_mb": 20,
    }
    assert client.put("/api/settings", json=settings).status_code == 200
    processed = client.post(
        "/api/process",
        files={"payslip_file": ("synthetic.png", _png_bytes(), "image/png")},
    )
    assert processed.status_code == 201
    assert created[0].exists()

    confirmed = client.post(f"/api/pay-periods/{processed.json()['id']}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["payslip"]["preview_url"] is None
    assert not created[0].exists()
