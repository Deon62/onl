"""access request website domain

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("access_requests", sa.Column("domain", sa.String(253), server_default="", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("access_requests") as batch:
        batch.drop_column("domain")
