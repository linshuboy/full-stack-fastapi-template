"""Add archive root dir to skill

Revision ID: c3d8a1f2e7b9
Revises: 9f6e2c1b7a44
Create Date: 2026-03-17 10:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d8a1f2e7b9"
down_revision = "9f6e2c1b7a44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill",
        sa.Column("archive_root_dir", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skill", "archive_root_dir")
