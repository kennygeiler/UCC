"""Optional lien detail fetch for secured party + filing date."""

from __future__ import annotations

import re

from app.scrapers.parsers import parse_date

_SECURED_LABEL_RE = re.compile(
    r"secured\s+party|secured\s+creditor|assignee",
    re.IGNORECASE,
)
_DATE_LABEL_RE = re.compile(r"filing\s+date|file\s+date", re.IGNORECASE)


async def fetch_secured_party_from_detail(page, *, lien_selector: str) -> dict[str, str | None]:
    """Click a grid lien link and scrape secured party / filing date from detail view.

    Returns dict with optional ``secured_party`` and ``filing_date`` (ISO date str).
    On failure returns empty strings (caller keeps grid values).
    """
    try:
        link = page.locator(lien_selector).first
        if not await link.count():
            return {"secured_party": None, "filing_date": None}

        async with page.expect_navigation(wait_until="networkidle", timeout=45_000):
            await link.click()

        detail = await page.evaluate(
            """() => {
                const rows = [];
                document.querySelectorAll('table tr, .row, dl').forEach(el => {
                    const text = (el.innerText || '').trim();
                    if (text) rows.push(text);
                });
                return rows.join('\\n');
            }"""
        )
        secured = _extract_labeled_value(detail, _SECURED_LABEL_RE)
        date_raw = _extract_labeled_value(detail, _DATE_LABEL_RE)
        filing_date = parse_date(date_raw.split()[0]) if date_raw else None

        await page.go_back(wait_until="networkidle", timeout=45_000)
        return {"secured_party": secured, "filing_date": filing_date}
    except Exception:
        try:
            await page.go_back(wait_until="networkidle", timeout=30_000)
        except Exception:
            pass
        return {"secured_party": None, "filing_date": None}


def _extract_labeled_value(text: str, label_re: re.Pattern[str]) -> str | None:
    for line in text.splitlines():
        if label_re.search(line):
            parts = re.split(r"[:\t]", line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
            # value on next line
            idx = text.splitlines().index(line)
            following = text.splitlines()[idx + 1 : idx + 2]
            if following and following[0].strip():
                return following[0].strip()
    return None
