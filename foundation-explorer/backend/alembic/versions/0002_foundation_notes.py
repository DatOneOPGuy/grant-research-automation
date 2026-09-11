"""Foundation notes: a team's research annotations on foundations.

Revision ID: 0002_foundation_notes
Revises: 0001_accounts
Create Date: 2026-09-11

Requested by the first customer: notes typed against any foundation, shown
as a column in the main table while browsing. Same category of data as
folders — a person decided it, nothing can regenerate it — hence Postgres
and a migration rather than the read model.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_foundation_notes"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foundation_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("ein", sa.String(length=9), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"],
                                ondelete="SET NULL"),
        sa.UniqueConstraint("team_id", "ein",
                            name="uq_foundation_notes_team_ein"),
    )
    op.create_index("ix_foundation_notes_team_id", "foundation_notes",
                    ["team_id"])


def downgrade() -> None:
    op.drop_table("foundation_notes")
