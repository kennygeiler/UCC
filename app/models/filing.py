"""UCC filing model — raw scraped filing records from state SOS portals."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UCCFiling(TimestampMixin, Base):
    """A single UCC filing record scraped from a state SOS portal."""

    __tablename__ = "ucc_filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filing_number: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    debtor_name: Mapped[str] = mapped_column(Text, nullable=False)
    secured_party: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collateral_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mca: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("business_accounts.id", ondelete="SET NULL"), nullable=True
    )
    lender_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "state",
            "filing_number",
            name="uq_ucc_filings_state_filing_number",
        ),
        Index("ix_ucc_filings_filing_number", "filing_number"),
        Index("ix_ucc_filings_state", "state"),
        Index("ix_ucc_filings_account_id", "account_id"),
    )
