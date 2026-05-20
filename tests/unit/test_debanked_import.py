"""Tests for deBanked MCA alias import."""

from pathlib import Path

import pytest

from app.mca.debanked_import import (
    _company_lender_class,
    parse_debanked_csv,
    parse_debanked_html,
)


FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "debanked_mca_ucc_snippet.html"
)


def test_parse_debanked_html_alias_count() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_debanked_html(html)
    aliases = [a for _, a, _ in rows]
    assert "EZ Business Cash Advance" in aliases
    assert "AdvanceMe" in aliases
    assert "Rhino Services" in aliases
    # First Data and Lending Club excluded entirely
    assert not any("first data" in a.lower() for a in aliases)
    assert not any("lending" in a.lower() for a in aliases)
    # Yellowstone + CAN (2 aliases) + CSC (2 aliases) = 5 mca + 2 registered_agent
    mca = [r for r in rows if r[2] == "mca_funder"]
    assert len(mca) >= 3


def test_csc_classified_registered_agent() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_debanked_html(html)
    csc = [r for r in rows if "Corporation Service" in r[0]]
    assert csc
    assert all(r[2] == "registered_agent" for r in csc)
    assert _company_lender_class("Corporation Service Company") == "registered_agent"


def test_skip_first_data_lending_club() -> None:
    assert _company_lender_class("First Data") is None
    assert _company_lender_class("Lending Club") is None


def test_parse_bundled_csv_has_many_companies() -> None:
    csv_path = Path(__file__).resolve().parents[2] / "data" / "debanked_mca_aliases.csv"
    rows = parse_debanked_csv(csv_path)
    companies = {r[0] for r in rows}
    assert len(companies) >= 80
    assert len(rows) >= 100


@pytest.mark.asyncio
async def test_import_debanked_calls_upsert() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.mca.debanked_import import import_debanked_mca_aliases

    upsert = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    class _Ctx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            return None

    with (
        patch("app.mca.debanked_import.upsert_mca_alias", upsert),
        patch("app.mca.debanked_import.reset_alias_class_cache", lambda: None),
        patch("app.mca.debanked_import.get_session", return_value=_Ctx()),
    ):
        stats = await import_debanked_mca_aliases(use_live_fetch=False)
    assert stats.added >= 100
    assert upsert.await_count == stats.added + stats.updated
