from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageOps

from app.config import AppSettings
from app.parsers import CoordinateRosterParser, GenericShiftParser
from app.parsers.registry import parse_payslip_text
from app.parsers.shift_postprocessing import consolidate_daily_shifts


def configure_tesseract(settings: AppSettings) -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def extract_payslip(path: Path, settings: AppSettings) -> tuple[dict, str, list[str]]:
    configure_tesseract(settings)
    warnings: list[str] = []
    if path.suffix.lower() == ".pdf":
        raw_text, used_ocr = _extract_pdf(path)
        if used_ocr:
            warnings.append("Embedded PDF text was unavailable; local OCR was used.")
    else:
        raw_text = _ocr_image(Image.open(path))
    if not raw_text.strip():
        warnings.append("No text could be extracted. Use manual entry.")
    structured, _ = parse_payslip_text(raw_text)
    return structured, raw_text, warnings


def extract_shifts(
    path: Path,
    settings: AppSettings,
    pay_period_start: date | None = None,
    pay_period_end: date | None = None,
) -> tuple[list[dict], str, list[str]]:
    configure_tesseract(settings)
    warnings: list[str] = []
    processed = _preprocess_image(Image.open(path))
    raw_text = pytesseract.image_to_string(processed, config="--psm 6")
    ocr_data = pytesseract.image_to_data(
        processed,
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )
    if not raw_text.strip():
        warnings.append("No shift text could be extracted. Add shifts manually.")
    coordinate_rows = CoordinateRosterParser().parse(
        ocr_data,
        int(processed.shape[1]),
        int(processed.shape[0]),
        pay_period_start,
        pay_period_end,
    )
    extracted_rows = coordinate_rows or GenericShiftParser().parse(raw_text)
    rows, rounded_boundaries, normalized_breaks = consolidate_daily_shifts(
        extracted_rows
    )
    if rounded_boundaries:
        warnings.append(
            f"{rounded_boundaries} punch time(s) were rounded using the attendance "
            "rule: clock-ins forward and clock-outs backward to a quarter hour."
        )
    if normalized_breaks:
        warnings.append(
            f"{normalized_breaks} between-shift gap(s) were normalized to a "
            "one- or two-hour unpaid break. Review the calculated hours."
        )
    return rows, raw_text, warnings


def _extract_pdf(path: Path) -> tuple[str, bool]:
    parts: list[str] = []
    used_ocr = False
    with fitz.open(path) as document:
        embedded = "\n".join(page.get_text("text") for page in document)
        if len(re.sub(r"\s+", "", embedded)) >= 40:
            return embedded, False
        used_ocr = True
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            parts.append(_ocr_image(image))
    return "\n".join(parts), used_ocr


def _ocr_image(image: Image.Image) -> str:
    array = _preprocess_image(image)
    return pytesseract.image_to_string(array, config="--psm 6")


def _preprocess_image(image: Image.Image) -> np.ndarray:
    image = ImageOps.exif_transpose(image).convert("RGB")
    try:
        osd = pytesseract.image_to_osd(image)
        rotation_match = re.search(r"Rotate:\s+(\d+)", osd)
        if rotation_match:
            rotation = int(rotation_match.group(1))
            if rotation:
                image = image.rotate(-rotation, expand=True)
    except pytesseract.TesseractError:
        pass

    grayscale = ImageOps.grayscale(image)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(1.6)
    array = np.array(grayscale)
    if array.std() < 55:
        array = cv2.adaptiveThreshold(
            array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )
    else:
        _, array = cv2.threshold(
            array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    return array
