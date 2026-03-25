"""Initial schema — all 13 tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_ucc_filings() -> None:
    op.create_table(
        "ucc_filings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filing_number", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("debtor_name", sa.Text(), nullable=False),
        sa.Column("secured_party", sa.Text(), nullable=True),
        sa.Column("filing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collateral_description", sa.Text(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ucc_filings_filing_number", "ucc_filings", ["filing_number"])
    op.create_index("ix_ucc_filings_state", "ucc_filings", ["state"])


def _create_leads() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("debtor_name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("lead_score", sa.Float(), nullable=True),
        sa.Column("mca_position_count", sa.Integer(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("estimated_revenue", sa.Float(), nullable=True),
        sa.Column("enrichment_status", sa.Text(), nullable=True),
        sa.Column("compliance_status", sa.Text(), nullable=True),
        sa.Column("export_status", sa.Text(), nullable=True),
        sa.Column("ghl_contact_id", sa.Text(), nullable=True),
        sa.Column("disposition", sa.Text(), nullable=True),
        sa.Column(
            "disposition_updated_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_state", "leads", ["state"])
    op.create_index("ix_leads_enrichment_status", "leads", ["enrichment_status"])
    op.create_index("ix_leads_compliance_status", "leads", ["compliance_status"])
    op.create_index("ix_leads_export_status", "leads", ["export_status"])


def _create_mca_aliases() -> None:
    op.create_table(
        "mca_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alias_name", sa.Text(), nullable=False),
        sa.Column("canonical_lender_name", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias_name"),
    )


def _create_internal_dnc() -> None:
    op.create_table(
        "internal_dnc",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("added_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_enrichment_cache() -> None:
    op.create_table(
        "enrichment_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_api", sa.Text(), nullable=False),
        sa.Column("input_key", sa.Text(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_enrichment_cache_source_key",
        "enrichment_cache",
        ["source_api", "input_key"],
    )


def _create_compliance_checks() -> None:
    op.create_table(
        "compliance_checks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("gate_name", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_checks_lead_id", "compliance_checks", ["lead_id"]
    )


def _create_job_queue() -> None:
    op.create_table(
        "job_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_queue_status", "job_queue", ["status"])
    op.create_index("ix_job_queue_scheduled_at", "job_queue", ["scheduled_at"])
    op.create_index("ix_job_queue_priority", "job_queue", ["priority"])


def _create_enrichment_retry_queue() -> None:
    op.create_table(
        "enrichment_retry_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_enrichment_retry_queue_lead_id", "enrichment_retry_queue", ["lead_id"]
    )


def _create_state_priority() -> None:
    op.create_table(
        "state_priority",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column(
            "leads_last_30_days", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "last_scrape_success", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("current_status", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state"),
    )


def _create_scraper_runs() -> None:
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_found", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraper_runs_state", "scraper_runs", ["state"])


def _create_agent_heartbeat() -> None:
    op.create_table(
        "agent_heartbeat",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )


def _create_pipeline_events() -> None:
    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("component", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_events_event_type", "pipeline_events", ["event_type"]
    )


def _create_langgraph_checkpoints() -> None:
    op.create_table(
        "langgraph_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_langgraph_checkpoints_thread_id", "langgraph_checkpoints", ["thread_id"]
    )


def upgrade() -> None:
    """Create all 13 tables."""
    _create_ucc_filings()
    _create_leads()
    _create_mca_aliases()
    _create_internal_dnc()
    _create_enrichment_cache()
    _create_compliance_checks()
    _create_job_queue()
    _create_enrichment_retry_queue()
    _create_state_priority()
    _create_scraper_runs()
    _create_agent_heartbeat()
    _create_pipeline_events()
    _create_langgraph_checkpoints()


def downgrade() -> None:
    """Drop all 13 tables in reverse order."""
    op.drop_table("langgraph_checkpoints")
    op.drop_table("pipeline_events")
    op.drop_table("agent_heartbeat")
    op.drop_table("scraper_runs")
    op.drop_table("state_priority")
    op.drop_table("enrichment_retry_queue")
    op.drop_table("job_queue")
    op.drop_table("compliance_checks")
    op.drop_table("enrichment_cache")
    op.drop_table("internal_dnc")
    op.drop_table("mca_aliases")
    op.drop_table("leads")
    op.drop_table("ucc_filings")
