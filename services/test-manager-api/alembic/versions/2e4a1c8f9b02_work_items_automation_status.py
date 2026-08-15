"""add automation_status to work_items

Revision ID: 2e4a1c8f9b02
Revises: f1a13823b537
Create Date: 2026-08-16 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2e4a1c8f9b02"
down_revision: Union[str, None] = "f1a13823b537"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column("automation_status", sa.String(length=64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("work_items", "automation_status")
