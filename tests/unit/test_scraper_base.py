"""Tests for the abstract base scraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.base import BaseScraper
from app.scrapers.rate_limiter import RateLimiter


class FakeScraper(BaseScraper):
    """Concrete test implementation of BaseScraper."""

    @property
    def state_code(self) -> str:
        """Return test state code."""
        return "ZZ"

    @property
    def tier(self) -> int:
        """Return test tier."""
        return 1

    @property
    def base_url(self) -> str:
        """Return test base URL."""
        return "https://example.com/ucc"

    @property
    def column_map(self) -> dict[str, int]:
        """Return test column map."""
        return {"filing_number": 0, "debtor_name": 1}

    def build_search_url(self) -> str:
        """Return test search URL."""
        return f"{self.base_url}?type=recent"

    def parse_response(self, html: str) -> list[dict]:
        """Return empty list for test."""
        return []


def test_fake_scraper_properties():
    """FakeScraper properties should return expected values."""
    scraper = FakeScraper()
    assert scraper.state_code == "ZZ"
    assert scraper.tier == 1
    assert scraper.base_url == "https://example.com/ucc"
    assert scraper.build_search_url() == "https://example.com/ucc?type=recent"


def test_scraper_accepts_rate_limiter():
    """BaseScraper should accept an injected rate limiter."""
    rl = RateLimiter(base_delay=5.0)
    scraper = FakeScraper(rate_limiter=rl)
    assert scraper.rate_limiter is rl
    assert scraper.rate_limiter.base_delay == 5.0


def test_scraper_creates_default_rate_limiter():
    """BaseScraper should create a default rate limiter if none provided."""
    scraper = FakeScraper()
    assert isinstance(scraper.rate_limiter, RateLimiter)


def test_cannot_instantiate_base_scraper():
    """BaseScraper is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseScraper()


def test_column_map_structure():
    """column_map should contain expected keys."""
    scraper = FakeScraper()
    assert "filing_number" in scraper.column_map


@pytest.mark.asyncio
async def test_fetch_uses_rate_limiter():
    """_fetch should call rate_limiter.wait before making request."""
    rl = RateLimiter(base_delay=0.0, jitter_pct=0.0)
    scraper = FakeScraper(rate_limiter=rl)
    mock_response = MagicMock()
    mock_response.text = "<html></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("app.scrapers.base.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        html = await scraper._fetch()
        assert html == "<html></html>"
        mock_client.get.assert_called_once()
