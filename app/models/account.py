"""Business account model — debtor-level consolidation scorecard."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BusinessAccount(TimestampMixin, Base):
    """A debtor business rolled up across UCC filings in one state."""

    __tablename__ = "business_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debtor_name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    consolidation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consolidation_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_components: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    mca_funder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    material_ucc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_since_last_filing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "debtor_name_normalized",
            "state",
            name="uq_business_accounts_debtor_state",
        ),
        Index("ix_business_accounts_state_score", "state", "consolidation_score"),
    )


class ScraperCheckpoint(Base):
    """Resume cursor for paginated FL index profiles."""

    __tablename__ = "scraper_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    index_profile: Mapped[str] = mapped_column(Text, nullable=False)
    last_row_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "state",
            "index_profile",
            name="uq_scraper_checkpoints_state_profile",
        ),
    )
