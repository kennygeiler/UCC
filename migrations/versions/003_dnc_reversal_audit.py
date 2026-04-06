"""Internal DNC soft-active flag + reversal audit (C-12).

Revision ID: 003_dnc_reversal_audit
Revises: 002_lead_mca_identity
Create Date: 2026-04-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_dnc_reversal_audit"
down_revision: Union[str, None] = "002_lead_mca_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "internal_dnc",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_table(
        "dnc_reversal_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("internal_dnc_id", sa.Integer(), nullable=False),
        sa.Column("reversed_by", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "reversed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["internal_dnc_id"],
            ["internal_dnc.id"],
            name="fk_dnc_reversal_audit_internal_dnc_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dnc_reversal_audit_internal_dnc_id",
        "dnc_reversal_audit",
        ["internal_dnc_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dnc_reversal_audit_internal_dnc_id", table_name="dnc_reversal_audit")
    op.drop_table("dnc_reversal_audit")
    op.drop_column("internal_dnc", "is_active")
