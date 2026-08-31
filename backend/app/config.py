from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(value: str | Path) -> Path:
    """Resolve and validate a path beneath the PayTracker project directory."""
    path = Path(value)
    resolved = (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Application storage paths must stay inside the project directory") from exc
    return resolved


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_prefix="PAYTRACKER_",
        extra="ignore",
    )

    app_name: str = "PayTracker"
    database_url: str = "sqlite:///data/paytracker.db"
    tesseract_cmd: str = ""
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    currency: str = "AUD"
    time_format: str = "24h"
    retain_uploads: bool = True
    backup_location: str = "backups"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("PayTracker only supports local SQLite databases")
        relative = value.removeprefix("sqlite:///")
        project_path(relative)
        return value

    @property
    def database_file(self) -> Path:
        return project_path(self.database_url.removeprefix("sqlite:///"))

    @property
    def uploads_dir(self) -> Path:
        return project_path("uploads")

    @property
    def exports_dir(self) -> Path:
        return project_path("exports")

    @property
    def backups_dir(self) -> Path:
        return project_path(self.backup_location)

    def ensure_directories(self) -> None:
        for path in (
            self.database_file.parent,
            self.uploads_dir / "payslips",
            self.uploads_dir / "timing-screenshots",
            self.exports_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()

