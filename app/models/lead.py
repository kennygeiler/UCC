"""Lead model — enriched, scored lead records."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lead(TimestampMixin, Base):
    """An enriched and scored lead derived from UCC filings."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debtor_name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    lead_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mca_position_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    enrichment_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="pending"
    )
    compliance_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="pending"
    )
    export_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="pending"
    )
    ghl_contact_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_leads_state", "state"),
        Index("ix_leads_enrichment_status", "enrichment_status"),
        Index("ix_leads_compliance_status", "compliance_status"),
        Index("ix_leads_export_status", "export_status"),
    )
