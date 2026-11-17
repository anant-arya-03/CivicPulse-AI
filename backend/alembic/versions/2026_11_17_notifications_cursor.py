"""Add stable notification read cursor.

Revision ID: m7_notification_cursor
Revises: 4b9540dbe92f
"""
from alembic import op
import sqlalchemy as sa

revision = "m7_notification_cursor"
down_revision = "4b9540dbe92f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("notifications_last_seen_seq", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "notifications_last_seen_seq")
