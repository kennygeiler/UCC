"""Consolidation scorecard — business accounts, checkpoints, lender metadata.

Revision ID: 005_consolidation_scorecard
Revises: 004_mca_scoring_provenance
Create Date: 2026-05-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_consolidation_scorecard"
down_revision: Union[str, None] = "004_mca_scoring_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("debtor_name_normalized", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("consolidation_score", sa.Float(), nullable=True),
        sa.Column("consolidation_tier", sa.Text(), nullable=True),
        sa.Column("score_components", postgresql.JSONB(), nullable=True),
        sa.Column("mca_funder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("material_ucc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_since_last_filing", sa.Integer(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "debtor_name_normalized",
            "state",
            name="uq_business_accounts_debtor_state",
        ),
    )
    op.create_index(
        "ix_business_accounts_state_score",
        "business_accounts",
        ["state", "consolidation_score"],
    )

    op.add_column("ucc_filings", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("ucc_filings", sa.Column("lender_class", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_ucc_filings_account_id",
        "ucc_filings",
        "business_accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ucc_filings_account_id", "ucc_filings", ["account_id"])

    op.add_column("mca_aliases", sa.Column("lender_class", sa.Text(), nullable=True))
    op.add_column(
        "mca_aliases",
        sa.Column("consolidation_weight", sa.Float(), nullable=True),
    )

    op.create_table(
        "scraper_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("index_profile", sa.Text(), nullable=False),
        sa.Column("last_row_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "state",
            "index_profile",
            name="uq_scraper_checkpoints_state_profile",
        ),
    )


def downgrade() -> None:
    op.drop_table("scraper_checkpoints")
    op.drop_column("mca_aliases", "consolidation_weight")
    op.drop_column("mca_aliases", "lender_class")
    op.drop_index("ix_ucc_filings_account_id", table_name="ucc_filings")
    op.drop_constraint("fk_ucc_filings_account_id", "ucc_filings", type_="foreignkey")
    op.drop_column("ucc_filings", "lender_class")
    op.drop_column("ucc_filings", "account_id")
    op.drop_index("ix_business_accounts_state_score", table_name="business_accounts")
    op.drop_table("business_accounts")
