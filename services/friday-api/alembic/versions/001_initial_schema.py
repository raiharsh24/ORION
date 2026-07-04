"""Initial schema: memory_kv and missions tables

Revision ID: 001
Revises:
Create Date: 2026-07-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_kv",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "missions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("data", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("missions")
    op.drop_table("memory_kv")
