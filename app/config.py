"""Configuration module using pydantic-settings.

Reads all settings from environment variables. Fails fast with a clear
ValidationError when required variables (DATABASE_URL, SENTRY_DSN) are missing.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required — app will not start without these
    DATABASE_URL: str
    SENTRY_DSN: str

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

    # Compliance API keys
    DATAMERCH_API_KEY: str | None = None
    DNC_SCRUB_API_KEY: str | None = None
    BLACKLIST_API_KEY: str | None = None

    # Proxy rotation (Tier-3 states)
    PROXY_URL: str | None = None

    # Pipeline: start APScheduler for tiered scrapes (disable in tests via env)
    SCRAPER_SCHEDULER_ENABLED: bool = True

    # MCA detector — fuzzy alias match (after exact match; O(n) over alias rows)
    MCA_FUZZY_MIN_ALIAS_LEN: int = 5
    MCA_FUZZY_SCORE_CUTOFF: int = 85

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
