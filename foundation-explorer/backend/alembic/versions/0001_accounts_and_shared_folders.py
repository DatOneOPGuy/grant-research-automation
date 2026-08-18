"""Accounts and shared saved folders.

Revision ID: 0001_accounts
Revises:
Create Date: 2026-08-18

The first mutable state in the product. explorer_v5.db is rebuilt wholesale
from the pipeline and needs no migrations; these tables hold work a user typed
and can never be regenerated, which is the whole reason they are here and in
Postgres rather than in the read model.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"],
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_team_id", "users", ["team_id"])

    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],
                                ondelete="SET NULL"),
    )
    op.create_index("ix_folders_team_id", "folders", ["team_id"])
    # Functional index: uniqueness is per team and case-insensitive, so
    # "Q1 asks" and "q1 asks" are the same folder.
    op.create_index("uq_folders_team_lower_name", "folders",
                    ["team_id", sa.text("lower(name)")], unique=True)

    op.create_table(
        "folder_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        # No foreign key to the foundations table: it lives in explorer_v5.db,
        # a different engine, and is dropped and recreated on every data
        # refresh. A constraint across the two would make a saved list block a
        # rebuild.
        sa.Column("ein", sa.String(length=9), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"],
                                ondelete="SET NULL"),
        sa.UniqueConstraint("folder_id", "ein",
                            name="uq_folder_items_folder_ein"),
    )
    op.create_index("ix_folder_items_folder_id", "folder_items", ["folder_id"])

    # One team for now. Every user is assigned to it on creation; the column
    # exists so a second team is a data change rather than a migration.
    op.execute(sa.text(
        "INSERT INTO teams (name) VALUES ('Foundation Explorer')"))


def downgrade() -> None:
    op.drop_table("folder_items")
    op.drop_index("uq_folders_team_lower_name", table_name="folders")
    op.drop_table("folders")
    op.drop_table("users")
    op.drop_table("teams")
