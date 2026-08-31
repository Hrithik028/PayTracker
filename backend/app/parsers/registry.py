from __future__ import annotations

from typing import Protocol

from app.parsers.generic_payslip import GenericPayslipParser


class LayoutPayslipParser(Protocol):
    """Contract for an optional layout-specific parser."""

    name: str

    def matches(self, text: str) -> bool: ...

    def parse(self, text: str) -> dict: ...


# Add narrow layout-specific parsers here. The conservative generic parser is
# always the final fallback and leaves unknown values blank.
LAYOUT_PARSERS: list[LayoutPayslipParser] = []


def parse_payslip_text(text: str) -> tuple[dict, str]:
    for parser in LAYOUT_PARSERS:
        if parser.matches(text):
            return parser.parse(text), parser.name
    parser = GenericPayslipParser()
    return parser.parse(text), parser.name

