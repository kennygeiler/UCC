"""UCC filing model — raw scraped filing records from state SOS portals."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, func
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
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_ucc_filings_filing_number", "filing_number"),
        Index("ix_ucc_filings_state", "state"),
    )
