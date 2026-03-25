"""HTML parsing utilities for extracting UCC filing data from state portals."""

from datetime import datetime, timezone
from html.parser import HTMLParser


class _TableParser(HTMLParser):
    """Minimal HTML table parser that extracts rows of cell text."""

    def __init__(self) -> None:
        """Initialize parser state."""
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track entry into tr/td/th tags."""
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th") and self._current_row is not None:
            self._current_cell = []
            self._in_cell = True

    def handle_endtag(self, tag: str) -> None:
        """Capture cell and row data on close tags."""
        if tag in ("td", "th") and self._in_cell:
            text = "".join(self._current_cell or []).strip()
            if self._current_row is not None:
                self._current_row.append(text)
            self._current_cell = None
            self._in_cell = False
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        """Accumulate text inside cells."""
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(data)


def parse_html_table(html: str) -> list[list[str]]:
    """Parse an HTML string and return all table rows as lists of cell text.

    Args:
        html: Raw HTML string containing a table.

    Returns:
        List of rows, each row a list of cell text strings.
    """
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def parse_date(date_str: str) -> datetime | None:
    """Parse a date string into a timezone-aware datetime.

    Tries common formats: MM/DD/YYYY, YYYY-MM-DD, MM-DD-YYYY.

    Args:
        date_str: Date string to parse.

    Returns:
        Parsed datetime with UTC timezone, or None if unparseable.
    """
    formats = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def rows_to_filing_dicts(
    rows: list[list[str]],
    state: str,
    column_map: dict[str, int],
) -> list[dict]:
    """Convert parsed table rows into filing dictionaries matching UCCFiling columns.

    Args:
        rows: Parsed table rows (first row may be header, skipped if non-numeric).
        state: Two-letter state code.
        column_map: Maps UCCFiling field names to column indices.

    Returns:
        List of dicts with keys: filing_number, state, debtor_name,
        secured_party, filing_date, collateral_description.
    """
    results: list[dict] = []
    for row in rows:
        fn_idx = column_map.get("filing_number")
        if fn_idx is None or fn_idx >= len(row):
            continue
        filing_number = row[fn_idx].strip()
        if not filing_number or not any(c.isdigit() for c in filing_number):
            continue
        filing = _build_filing_dict(row, state, filing_number, column_map)
        results.append(filing)
    return results


def _build_filing_dict(
    row: list[str],
    state: str,
    filing_number: str,
    column_map: dict[str, int],
) -> dict:
    """Build a single filing dict from a row.

    Args:
        row: A single parsed table row.
        state: Two-letter state code.
        filing_number: Already-extracted filing number.
        column_map: Maps field names to column indices.

    Returns:
        Dict matching UCCFiling column names.
    """
    def _get(field: str) -> str | None:
        idx = column_map.get(field)
        if idx is not None and idx < len(row):
            val = row[idx].strip()
            return val if val else None
        return None

    date_str = _get("filing_date")
    return {
        "filing_number": filing_number,
        "state": state,
        "debtor_name": _get("debtor_name") or "Unknown",
        "secured_party": _get("secured_party"),
        "filing_date": parse_date(date_str) if date_str else None,
        "collateral_description": _get("collateral_description"),
    }
