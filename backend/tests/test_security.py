from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.config import get_settings, project_path
from app.security.files import validate_upload


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_real_file_type_is_verified() -> None:
    upload = UploadFile(filename="shift.png", file=io.BytesIO(png_bytes()))
    result = await validate_upload(upload, get_settings())
    assert result.detected_format == "png"
    assert len(result.sha256) == 64


@pytest.mark.asyncio
async def test_extension_spoofing_is_rejected() -> None:
    upload = UploadFile(filename="not-really.pdf", file=io.BytesIO(png_bytes()))
    with pytest.raises(HTTPException, match="file extension"):
        await validate_upload(upload, get_settings())


def test_project_path_prevents_traversal() -> None:
    with pytest.raises(ValueError, match="inside the project"):
        project_path("../../outside.db")

