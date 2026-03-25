"""Operations models — state priority, scraper runs, heartbeat, events, checkpoints."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StatePriority(Base):
    """Per-state priority tier for repair ordering and scrape scheduling."""

    __tablename__ = "state_priority"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    leads_last_30_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_scrape_success: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="active"
    )


class ScraperRun(TimestampMixin, Base):
    """Log of each scraper execution per state."""

    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    records_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_scraper_runs_state", "state"),)


class AgentHeartbeat(Base):
    """Self-healing agent heartbeat record."""

    __tablename__ = "agent_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")


class PipelineEvent(Base):
    """Event log for pipeline state changes."""

    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_pipeline_events_event_type", "event_type"),)


class LanggraphCheckpoint(Base):
    """Minimal LangGraph checkpoint table for PostgresSaver compatibility."""

    __tablename__ = "langgraph_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_langgraph_checkpoints_thread_id", "thread_id"),)
