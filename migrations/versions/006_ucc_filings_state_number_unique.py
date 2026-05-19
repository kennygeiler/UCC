"""Unique constraint on ucc_filings (state, filing_number).

Revision ID: 006_ucc_unique
Revises: 005_consolidation
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006_ucc_unique"
down_revision: Union[str, None] = "005_consolidation_scorecard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM ucc_filings a
        USING ucc_filings b
        WHERE a.id > b.id
          AND a.state = b.state
          AND a.filing_number = b.filing_number
        """
    )
    op.create_unique_constraint(
        "uq_ucc_filings_state_filing_number",
        "ucc_filings",
        ["state", "filing_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ucc_filings_state_filing_number",
        "ucc_filings",
        type_="unique",
    )
