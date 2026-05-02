"""
Unit tests for the EWALLET ETAX PDF parser in src.data_extractor.

The integration test uses a real KBank e-Tax invoice PDF placed at
tests/fixtures/sample_ewallet_etax.pdf. Drop a sample PDF there and commit
it before running the suite — without it, the integration test is skipped.

The unit tests around _thai_digits_to_arabic and _normalize_thai_year always run.
"""

import os
import re

import pytest

from src.data_extractor import (
    _thai_digits_to_arabic,
    _normalize_thai_year,
    extract_ewallet_etax_pdf_data,
)


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_PDF = os.path.join(FIXTURE_DIR, "sample_ewallet_etax.pdf")


def test_thai_digits_to_arabic_full_set():
    assert _thai_digits_to_arabic("๐๑๒๓๔๕๖๗๘๙") == "0123456789"


def test_thai_digits_to_arabic_mixed():
    assert _thai_digits_to_arabic("INV-๒๐๒๖๐๔๑๕-001") == "INV-20260415-001"


def test_thai_digits_to_arabic_passthrough_for_arabic():
    assert _thai_digits_to_arabic("12/04/2026") == "12/04/2026"


def test_normalize_thai_year_buddhist_to_gregorian():
    assert _normalize_thai_year("15/04/2569") == "15/04/2026"


def test_normalize_thai_year_already_gregorian_unchanged():
    assert _normalize_thai_year("15/04/2026") == "15/04/2026"


def test_normalize_thai_year_handles_dash_separator():
    assert _normalize_thai_year("15-04-2569") == "15/04/2026"


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_PDF),
    reason=(
        "Drop a real KBank EWALLET ETAX PDF at tests/fixtures/sample_ewallet_etax.pdf "
        "to enable this integration test."
    ),
)
def test_extract_ewallet_etax_pdf_data_against_sample():
    parsed = extract_ewallet_etax_pdf_data(SAMPLE_PDF)
    assert parsed is not None, "Parser returned None for fixture PDF"

    assert isinstance(parsed["tax_invoice_no"], str) and parsed["tax_invoice_no"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed["tax_invoice_date"])

    assert parsed["comm"] > 0
    assert parsed["vat"] > 0
    assert parsed["net_after_vat"] > 0
    # VAT is 7% of the commission on Thai e-Tax invoices (within rounding).
    assert abs(parsed["vat"] - parsed["comm"] * 0.07) < 0.05


def test_extract_ewallet_etax_pdf_data_missing_file_returns_none():
    assert extract_ewallet_etax_pdf_data("/no/such/file.pdf") is None
