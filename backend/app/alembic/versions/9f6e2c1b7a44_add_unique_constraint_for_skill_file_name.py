"""Add unique constraint for skill file name

Revision ID: 9f6e2c1b7a44
Revises: 4b7c6f9a2d11
Create Date: 2026-03-16 17:05:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9f6e2c1b7a44"
down_revision = "4b7c6f9a2d11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(op.f("uq_skill_file_name"), "skill", ["file_name"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_skill_file_name"), "skill", type_="unique")
