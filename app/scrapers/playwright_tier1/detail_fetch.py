"""Optional lien detail fetch for secured party + filing date."""

from __future__ import annotations

import re

from app.scrapers.parsers import parse_date

_SECURED_LABEL_RE = re.compile(
    r"secured\s+party|secured\s+creditor|assignee",
    re.IGNORECASE,
)
_DATE_LABEL_RE = re.compile(r"filing\s+date|file\s+date|date\s+filed", re.IGNORECASE)


def parse_detail_fields_from_text(text: str) -> dict[str, str | None]:
    """Extract secured party and filing date from lien detail page text/HTML."""
    if "<" in text and ">" in text:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            lines: list[str] = []
            for tr in soup.select("table tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                cells = [c for c in cells if c]
                if len(cells) >= 2:
                    label = cells[0].rstrip(":").strip()
                    lines.append(f"{label}: {cells[1]}")
                elif cells:
                    lines.append(cells[0])
            text = "\n".join(lines) if lines else soup.get_text("\n", strip=True)
        except Exception:
            pass
    secured = _extract_labeled_value(text, _SECURED_LABEL_RE)
    date_raw = _extract_labeled_value(text, _DATE_LABEL_RE)
    filing_date = None
    if date_raw:
        filing_date = parse_date(date_raw.split()[0])
        if filing_date is None:
            filing_date = parse_date(date_raw)
    return {"secured_party": secured, "filing_date": filing_date}


async def fetch_secured_party_from_detail(page, *, lien_selector: str) -> dict[str, str | None]:
    """Click a grid lien link and scrape secured party / filing date from detail view.

    Returns dict with optional ``secured_party`` and ``filing_date`` (ISO date str).
    On failure returns empty values (caller keeps grid values).
    """
    try:
        link = page.locator(lien_selector).first
        if not await link.count():
            return {"secured_party": None, "filing_date": None}

        async with page.expect_navigation(wait_until="networkidle", timeout=45_000):
            await link.click()

        detail = await page.evaluate(
            """() => {
                const parts = [];
                document.querySelectorAll('table tr').forEach(tr => {
                    const cells = Array.from(tr.querySelectorAll('th, td'))
                        .map(c => (c.innerText || '').trim())
                        .filter(Boolean);
                    if (cells.length >= 2) {
                        parts.push(cells[0] + ': ' + cells.slice(1).join(' '));
                    } else if (cells.length === 1) {
                        parts.push(cells[0]);
                    }
                });
                document.querySelectorAll('dl dt, dl dd, .row, .form-group label')
                    .forEach(el => {
                        const t = (el.innerText || '').trim();
                        if (t) parts.push(t);
                    });
                return parts.join('\\n');
            }"""
        )
        parsed = parse_detail_fields_from_text(detail)
        if not parsed.get("secured_party"):
            body_text = await page.evaluate("() => document.body.innerText || ''")
            parsed = parse_detail_fields_from_text(body_text)

        await page.go_back(wait_until="networkidle", timeout=45_000)
        return parsed
    except Exception:
        try:
            await page.go_back(wait_until="networkidle", timeout=30_000)
        except Exception:
            pass
        return {"secured_party": None, "filing_date": None}


def _extract_labeled_value(text: str, label_re: re.Pattern[str]) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if label_re.search(line):
            parts = re.split(r"[:\t]", line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip().lstrip(":").strip()
            if i + 1 < len(lines) and lines[i + 1].strip():
                return lines[i + 1].strip()
    return None
