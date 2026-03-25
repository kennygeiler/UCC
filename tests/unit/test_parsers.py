"""Tests for HTML parsing utilities."""

from datetime import datetime, timezone

from app.scrapers.parsers import (
    parse_date,
    parse_html_table,
    rows_to_filing_dicts,
)


SAMPLE_HTML = """
<table>
  <tr><th>Filing #</th><th>Date</th><th>Debtor</th><th>Secured</th><th>Collateral</th></tr>
  <tr><td>2024-001</td><td>01/15/2024</td><td>Test Corp</td><td>Lender LLC</td><td>All assets</td></tr>
  <tr><td>2024-002</td><td>02/20/2024</td><td>Acme Inc</td><td>Bank of X</td><td>Equipment</td></tr>
</table>
"""


def test_parse_html_table_extracts_rows():
    """parse_html_table should extract all rows including header."""
    rows = parse_html_table(SAMPLE_HTML)
    assert len(rows) == 3
    assert rows[0][0] == "Filing #"
    assert rows[1][0] == "2024-001"


def test_parse_html_table_empty_html():
    """parse_html_table returns empty list for html with no table."""
    rows = parse_html_table("<div>No table here</div>")
    assert rows == []


def test_parse_date_mm_dd_yyyy():
    """parse_date handles MM/DD/YYYY format."""
    result = parse_date("01/15/2024")
    assert result == datetime(2024, 1, 15, tzinfo=timezone.utc)


def test_parse_date_iso_format():
    """parse_date handles YYYY-MM-DD format."""
    result = parse_date("2024-01-15")
    assert result == datetime(2024, 1, 15, tzinfo=timezone.utc)


def test_parse_date_mm_dash_dd_yyyy():
    """parse_date handles MM-DD-YYYY format."""
    result = parse_date("01-15-2024")
    assert result == datetime(2024, 1, 15, tzinfo=timezone.utc)


def test_parse_date_invalid_returns_none():
    """parse_date returns None for unparseable strings."""
    assert parse_date("not-a-date") is None
    assert parse_date("") is None


def test_rows_to_filing_dicts_basic():
    """rows_to_filing_dicts converts rows to filing dicts."""
    rows = parse_html_table(SAMPLE_HTML)
    column_map = {
        "filing_number": 0,
        "filing_date": 1,
        "debtor_name": 2,
        "secured_party": 3,
        "collateral_description": 4,
    }
    filings = rows_to_filing_dicts(rows, "CA", column_map)
    assert len(filings) == 2
    assert filings[0]["filing_number"] == "2024-001"
    assert filings[0]["state"] == "CA"
    assert filings[0]["debtor_name"] == "Test Corp"
    assert filings[0]["secured_party"] == "Lender LLC"
    assert filings[0]["collateral_description"] == "All assets"


def test_rows_to_filing_dicts_skips_header():
    """Header row (no digits in first cell) should be skipped."""
    rows = [["Filing #", "Date", "Debtor", "Secured", "Collateral"]]
    column_map = {"filing_number": 0, "debtor_name": 2}
    filings = rows_to_filing_dicts(rows, "TX", column_map)
    assert len(filings) == 0


def test_rows_to_filing_dicts_empty_rows():
    """Empty input rows should produce empty output."""
    filings = rows_to_filing_dicts([], "FL", {"filing_number": 0})
    assert filings == []


def test_rows_to_filing_dicts_missing_optional_fields():
    """Missing optional fields should be None."""
    rows = [["2024-003", "", "Debtor Co", "", ""]]
    column_map = {
        "filing_number": 0,
        "filing_date": 1,
        "debtor_name": 2,
        "secured_party": 3,
        "collateral_description": 4,
    }
    filings = rows_to_filing_dicts(rows, "NY", column_map)
    assert len(filings) == 1
    assert filings[0]["secured_party"] is None
    assert filings[0]["filing_date"] is None
