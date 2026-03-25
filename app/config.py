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

    # Self-healing agent
    ANTHROPIC_API_KEY: str | None = None

    # GitHub integration
    GITHUB_TOKEN: str | None = None
    GITHUB_REPO: str | None = None

    # Alerts
    SENDGRID_API_KEY: str | None = None
    MANAGER_EMAIL: str | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
