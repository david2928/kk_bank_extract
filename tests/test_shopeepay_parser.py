"""Unit tests for the ShopeePay daily-settlement HTML email parser."""

import os

import pytest

from src.data_extractor import extract_shopeepay_settlement_body

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_HTML = os.path.join(FIXTURE_DIR, "sample_shopeepay_settlement.html")
SAMPLE_SUBJECT = (
    "[LENGOLF Co. Ltd (บริษัท เล่นกอล์ฟ จำกัด)] "
    "รายงานการโอนเงินสำหรับ ShopeePay Payment [2026-05-15]"
)


@pytest.fixture(scope="module")
def sample_html():
    if not os.path.exists(SAMPLE_HTML):
        pytest.skip(f"fixture missing: {SAMPLE_HTML}")
    with open(SAMPLE_HTML, encoding="utf-8") as f:
        return f.read()


def test_parses_main_section_amounts(sample_html):
    """All 8 fields + bank tail + settlement_date extract exactly."""
    p = extract_shopeepay_settlement_body(sample_html, subject=SAMPLE_SUBJECT)
    assert p is not None
    assert p["settlement_date"] == "2026-05-14"
    assert p["gross_amount"] == 2300.00
    assert p["refund_amount"] == 0.00
    assert p["merchant_support_amount"] == 0.00
    assert p["commission_amount"] == 23.00
    assert p["vat_on_commission"] == 1.61
    assert p["wht_amount"] == 0.69
    assert p["rollover_amount"] == 0.00
    assert p["net_amount"] == 2275.39
    assert p["bank_account_tail"] == "0294"


def test_empirical_net_equation_holds(sample_html):
    """Observed in all 8 emails: WHT is NOT subtracted from the deposit."""
    p = extract_shopeepay_settlement_body(sample_html, subject=SAMPLE_SUBJECT)
    derived = (
        p["gross_amount"]
        - p["refund_amount"]
        + p["merchant_support_amount"]
        - p["commission_amount"]
        - p["vat_on_commission"]
        + p["rollover_amount"]
    )
    assert abs(derived - p["net_amount"]) < 0.01


def test_returns_none_for_unrelated_body():
    assert extract_shopeepay_settlement_body("hello world", subject="x") is None
    assert extract_shopeepay_settlement_body("", subject="x") is None
    assert extract_shopeepay_settlement_body(None, subject="x") is None


def test_ignores_not_yet_collected_section():
    """If a future email has non-zero values in the second table, we must NOT pick them up."""
    # Build a minimal HTML where the second table has different values; first table must win.
    html_doc = (
        "<html><body>"
        "<p>นำส่งสรุปรายงานการขายประจำวันที่ 2026-05-01 - 2026-05-01.</p>"
        "<table>"
        "<tr><th>สรุปยอดรายการโอนเงินให้ทางร้านค้า</th></tr>"
        "<tr><td>บัญชีการรับเงิน</td><td>เลขบัญชี:******0294</td></tr>"
        "<tr><td>ยอดเงินที่ต้องชำระ</td><td>100.00</td></tr>"
        "<tr><td>การคืนเงิน</td><td>0.00</td></tr>"
        "<tr><td>เงินสนับสนุนจากร้านค้า ตัวแทนร้านค้า หรือแบรนด์</td><td>0.00</td></tr>"
        "<tr><td>ค่าธรรมเนียม</td><td>10.00</td></tr>"
        "<tr><td>VAT</td><td>0.70</td></tr>"
        "<tr><td>WHT</td><td>0.30</td></tr>"
        "<tr><td>ยอดยกมา</td><td>0.00</td></tr>"
        "<tr><td>ยอดรวมที่โอนให้ร้านค้า</td><td>89.30</td></tr>"
        "</table>"
        "<table>"
        "<tr><th>สรุปรายการที่ไม่ยังเรียกเก็บในยอดโอน</th></tr>"
        "<tr><td>ค่าธรรมเนียม</td><td>999.99</td></tr>"
        "<tr><td>VAT</td><td>999.99</td></tr>"
        "<tr><td>ยอดยกมา</td><td>999.99</td></tr>"
        "</table>"
        "</body></html>"
    )
    p = extract_shopeepay_settlement_body(html_doc, subject="x")
    assert p is not None
    assert p["commission_amount"] == 10.00  # not 999.99
    assert p["vat_on_commission"] == 0.70   # not 999.99
    assert p["rollover_amount"] == 0.00     # not 999.99
    assert p["net_amount"] == 89.30


def test_subject_date_fallback_when_body_range_missing():
    """If the 'ประจำวันที่ X - Y' line is absent, fall back to subject [date] minus one day."""
    html_doc = (
        "<html><body>"
        "<table>"
        "<tr><th>สรุปยอดรายการโอนเงินให้ทางร้านค้า</th></tr>"
        "<tr><td>บัญชีการรับเงิน</td><td>เลขบัญชี:******0294</td></tr>"
        "<tr><td>ยอดเงินที่ต้องชำระ</td><td>100.00</td></tr>"
        "<tr><td>การคืนเงิน</td><td>0.00</td></tr>"
        "<tr><td>เงินสนับสนุนจากร้านค้า ตัวแทนร้านค้า หรือแบรนด์</td><td>0.00</td></tr>"
        "<tr><td>ค่าธรรมเนียม</td><td>1.00</td></tr>"
        "<tr><td>VAT</td><td>0.07</td></tr>"
        "<tr><td>WHT</td><td>0.03</td></tr>"
        "<tr><td>ยอดยกมา</td><td>0.00</td></tr>"
        "<tr><td>ยอดรวมที่โอนให้ร้านค้า</td><td>98.93</td></tr>"
        "</table>"
        "</body></html>"
    )
    p = extract_shopeepay_settlement_body(
        html_doc,
        subject="[LENGOLF] ShopeePay Payment [2026-05-15]",
    )
    assert p is not None
    assert p["settlement_date"] == "2026-05-14"
