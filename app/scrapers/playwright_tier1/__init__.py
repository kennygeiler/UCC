"""Shared Playwright Tier 1 scrape primitives (NY, NJ, CA, TX)."""

from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings, load_playwright_scrape_settings

__all__ = [
    "PlaywrightTier1Scraper",
    "PlaywrightScrapeSettings",
    "load_playwright_scrape_settings",
]
