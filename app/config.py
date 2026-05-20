"""Configuration module using pydantic-settings.

Reads all settings from environment variables. Fails fast with a clear
ValidationError when ``DATABASE_URL`` is missing. ``SENTRY_DSN`` is optional
so local demos can run without Sentry; production should set a real DSN
(``https://key@oORG.ingest.sentry.io/PROJECT_ID`` with a numeric project id).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required — app will not start without database
    DATABASE_URL: str
    # Optional locally; when unset/empty, entrypoints skip sentry_sdk.init (PLAT-08 in prod)
    SENTRY_DSN: str | None = None

    # GoHighLevel integration
    GHL_API_KEY: str | None = None
    GHL_LOCATION_ID: str | None = None
    GHL_WEBHOOK_SECRET: str | None = None
    GHL_WORKFLOW_TIER1: str | None = None
    GHL_WORKFLOW_TIER2: str | None = None
    GHL_WORKFLOW_TIER3: str | None = None

    # Enrichment API keys
    APOLLO_API_KEY: str | None = None
    PDL_API_KEY: str | None = None
    OPENCORPORATES_API_KEY: str | None = None
    WHITEPAGES_API_KEY: str | None = None
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None

    # Compliance API keys (C-15: optional fail-closed when DATAMERCH key missing)
    DATAMERCH_API_KEY: str | None = None
    COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH: bool = False
    DNC_SCRUB_API_KEY: str | None = None
    BLACKLIST_API_KEY: str | None = None

    # Proxy rotation (Tier-3 states)
    PROXY_URL: str | None = None

    # Pipeline: start APScheduler for tiered scrapes (disable in tests via env)
    SCRAPER_SCHEDULER_ENABLED: bool = True
    # Rolling filing-date window for states that query by date (e.g. California API).
    # Larger values backfill further; persistence still dedupes by state + filing_number.
    SCRAPER_FILING_LOOKBACK_DAYS: int = 3

    # Florida scraper — deep Standard pagination + multi-index profiles (not A–Z).
    # See app/scrapers/states/florida.py.
    FL_SCRAPE_MAX_PAGES: int = 500
    FL_SCRAPE_PAGE_CAP_PER_RUN: int = 50
    FL_SCRAPE_INDEX_PROFILES: str = (
        "OrganizationDebtorName|FiledCompactDebtorNameList,"
        "OrganizationDebtorName|FiledActualDebtorNameList,"
        "IndividualDebtorName|FiledCompactDebtorNameList"
    )
    FL_SCRAPE_ENRICH_CONCURRENCY: int = 5
    FL_SCRAPE_FETCH_FILING_DATE: bool = True
    FL_SCRAPE_EXACT_TERMS: str = ""
    # Deprecated: Standard mode ignores text; kept for backwards-compatible env only.
    FL_SCRAPE_SEARCH_TERMS: str = ""

    # Playwright Tier 1 (NY, NJ, CA, TX) — shared defaults; per-state overrides below.
    PLAYWRIGHT_SCRAPE_MAX_PAGES: int = 50
    PLAYWRIGHT_SCRAPE_MAX_TERMS: int = 20
    PLAYWRIGHT_SCRAPE_MCA_TERM_LIMIT: int = 20
    PLAYWRIGHT_SCRAPE_FETCH_DETAIL: bool = True
    PLAYWRIGHT_SCRAPE_SEARCH_TERMS: str = ""

    NY_SCRAPE_MAX_PAGES: int = 50
    NY_SCRAPE_MAX_TERMS: int = 20
    NY_SCRAPE_MCA_TERM_LIMIT: int = 200
    # Max search variants per MCA funder (full alias + first token + aliases); unset = no cap
    NY_SCRAPE_VARIANT_LIMIT: int | None = None
    NY_SCRAPE_FETCH_DETAIL: bool = True
    NY_SCRAPE_SEARCH_TERMS: str = ""
    NY_SCRAPE_PAGE_CAP_PER_RUN: int | None = None
    NY_SCRAPE_SEARCH_PROFILES: str = "secured_party_org_sw,debtor_org_sw"
    NY_SCRAPE_PREFIX_TERMS: str = ""
    # Pagination direction: forward (page 1→N), reverse (last→first), recent_only (last K pages).
    NY_SCRAPE_PAGE_ORDER: str = "forward"
    NY_SCRAPE_RECENT_PAGES: int = 10

    NJ_SCRAPE_MAX_PAGES: int = 50
    NJ_SCRAPE_MAX_TERMS: int = 20
    NJ_SCRAPE_MCA_TERM_LIMIT: int = 20
    NJ_SCRAPE_FETCH_DETAIL: bool = False
    NJ_SCRAPE_SEARCH_TERMS: str = ""
    NJ_SCRAPE_SEARCH_PROFILES: str = ""

    CA_SCRAPE_MAX_PAGES: int = 50
    CA_SCRAPE_MAX_TERMS: int = 20
    CA_SCRAPE_MCA_TERM_LIMIT: int = 20
    CA_SCRAPE_SEARCH_TERMS: str = ""
    CA_SCRAPE_PAGE_CAP_PER_RUN: int | None = None

    TX_SCRAPE_MAX_PAGES: int = 50
    TX_SCRAPE_MAX_TERMS: int = 20
    TX_SCRAPE_MCA_TERM_LIMIT: int = 20
    TX_SCRAPE_SEARCH_TERMS: str = ""

    # MCA detector — fuzzy alias match (after exact match; O(n) over alias rows)
    MCA_FUZZY_MIN_ALIAS_LEN: int = 5
    MCA_FUZZY_SCORE_CUTOFF: int = 90
    MCA_FUZZY_REQUIRE_TOKEN_OVERLAP: bool = True
    # Comma-separated lender_class values that skip alias/fuzzy MCA matching
    MCA_BLOCKED_LENDER_CLASSES: str = "government,registered_agent,insurance,bank"

    # MCA alias auto-updater job (same scheduler as scrapers)
    MCA_ALIAS_UPDATE_ENABLED: bool = True
    MCA_ALIAS_UPDATE_INTERVAL_HOURS: int = 24

    # Enrichment rolling error rate → HALT (C-03) + retry job
    ENRICH_BREAKER_ERROR_WINDOW_SECONDS: int = 300
    ENRICH_BREAKER_ERROR_RATE_THRESHOLD: float = 0.2
    ENRICH_RATE_MIN_ATTEMPTS_BEFORE_HALT: int = 5
    ENRICH_RETRY_JOB_ENABLED: bool = True
    ENRICH_RETRY_INTERVAL_MINUTES: int = 60

    # Self-healing agent
    ANTHROPIC_API_KEY: str | None = None

    # GitHub integration
    GITHUB_TOKEN: str | None = None
    GITHUB_REPO: str | None = None

    # Alerts
    SENDGRID_API_KEY: str | None = None
    MANAGER_EMAIL: str | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
