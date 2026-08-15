"""add acceptance_test_required to work_items

Revision ID: 3c1d4f2a9e10
Revises: 2e4a1c8f9b02
Create Date: 2026-08-16 02:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c1d4f2a9e10"
down_revision: Union[str, None] = "2e4a1c8f9b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column("acceptance_test_required", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("work_items", "acceptance_test_required")
