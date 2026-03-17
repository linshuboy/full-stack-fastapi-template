"""Add skill repository models

Revision ID: 4b7c6f9a2d11
Revises: fe56fa70289e
Create Date: 2026-03-16 16:12:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4b7c6f9a2d11"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skillcategory",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_skillcategory_name"), "skillcategory", ["name"], unique=True
    )

    op.create_table(
        "skill",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_object_name", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_content_type", sa.String(length=255), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["skillcategory.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_object_name"),
    )
    op.create_index(op.f("ix_skill_category_id"), "skill", ["category_id"], unique=False)
    op.create_index(
        op.f("ix_skill_is_published"), "skill", ["is_published"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_skill_is_published"), table_name="skill")
    op.drop_index(op.f("ix_skill_category_id"), table_name="skill")
    op.drop_table("skill")
    op.drop_index(op.f("ix_skillcategory_name"), table_name="skillcategory")
    op.drop_table("skillcategory")
