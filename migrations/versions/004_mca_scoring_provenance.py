"""MCA scoring provenance and is_mca on filings.

Revision ID: 004_mca_scoring_provenance
Revises: 003_dnc_reversal_audit
Create Date: 2026-05-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_mca_scoring_provenance"
down_revision: Union[str, None] = "003_dnc_reversal_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ucc_filings", sa.Column("is_mca", sa.Boolean(), nullable=True))
    op.create_index("ix_ucc_filings_is_mca", "ucc_filings", ["is_mca"])

    op.add_column("leads", sa.Column("mca_match_type", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("mca_lender_canonical", sa.Text(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("mca_match_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leads", "mca_match_confidence")
    op.drop_column("leads", "mca_lender_canonical")
    op.drop_column("leads", "mca_match_type")
    op.drop_index("ix_ucc_filings_is_mca", table_name="ucc_filings")
    op.drop_column("ucc_filings", "is_mca")
