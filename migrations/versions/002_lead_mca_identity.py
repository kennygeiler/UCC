"""Lead MCA identity and filing link.

Revision ID: 002_lead_mca_identity
Revises: 001_initial
Create Date: 2026-04-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_lead_mca_identity"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("debtor_name_normalized", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("leads", sa.Column("mca_tier", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("source_filing_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leads_source_filing_id",
        "leads",
        "ucc_filings",
        ["source_filing_id"],
        ["id"],
    )
    op.create_unique_constraint("uq_leads_source_filing_id", "leads", ["source_filing_id"])
    op.create_index(
        "ix_leads_debtor_name_normalized",
        "leads",
        ["debtor_name_normalized"],
    )
    op.execute(
        sa.text(
            "UPDATE leads SET debtor_name_normalized = lower(trim(both ' ' from debtor_name))"
        )
    )
    op.execute(
        sa.text(
            """UPDATE leads SET mca_tier = CASE
            WHEN mca_position_count >= 3 THEN 'hot'
            WHEN mca_position_count = 2 THEN 'warm'
            ELSE 'cold'
        END
        WHERE mca_position_count IS NOT NULL"""
        )
    )
    op.alter_column(
        "leads",
        "debtor_name_normalized",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index("ix_leads_debtor_name_normalized", table_name="leads")
    op.drop_constraint("uq_leads_source_filing_id", "leads", type_="unique")
    op.drop_constraint("fk_leads_source_filing_id", "leads", type_="foreignkey")
    op.drop_column("leads", "source_filing_id")
    op.drop_column("leads", "mca_tier")
    op.drop_column("leads", "debtor_name_normalized")
