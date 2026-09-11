"""Postgres schema for accounts and shared saved folders.

Separate from models.py, which describes the read model's response shapes.
This is the only mutable state in the product: explorer_v5.db is a rebuildable
artifact, these tables are not, which is why they get Alembic and it does not.

Folders are shared across a team, not owned by a user. Everyone on a team sees
and edits the same folders; created_by and added_by exist for attribution, not
for visibility. Prospect research is a team activity, and a saved list that
only its author can see is a list the team cannot act on.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now_col(**kw) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kw)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _now_col(nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cloudflare Access is the only identity source, so the email in a
    # verified token is the whole account. No password column by design.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = _now_col(nullable=False)
    last_seen_at: Mapped[datetime] = _now_col(nullable=False)

    team: Mapped[Team] = relationship(back_populates="users")


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (
        # Case-insensitive uniqueness per team, matching what the local store
        # did within one browser: creating a folder whose name already exists
        # returns the existing one. With shared folders this matters more, not
        # less -- two people creating "Q1 asks" a minute apart should collide
        # into one folder rather than fork the team's filing.
        Index("uq_folders_team_lower_name", "team_id", func.lower("name"),
              unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _now_col(nullable=False)

    items: Mapped[list[FolderItem]] = relationship(
        back_populates="folder", cascade="all, delete-orphan",
        passive_deletes=True)
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])


class FolderItem(Base):
    __tablename__ = "folder_items"
    __table_args__ = (
        # Makes an add idempotent: ON CONFLICT DO NOTHING turns a double-click
        # or a concurrent save by a teammate into a no-op rather than a 500.
        UniqueConstraint("folder_id", "ein", name="uq_folder_items_folder_ein"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True)
    # The EIN is a foreign key into explorer_v5.db, which Postgres cannot
    # enforce and must not try to -- the read model is rebuilt wholesale and a
    # constraint across the two would make a saved list block a data refresh.
    ein: Mapped[str] = mapped_column(String(9), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = _now_col(nullable=False)

    folder: Mapped[Folder] = relationship(back_populates="items")
    adder: Mapped[User | None] = relationship(foreign_keys=[added_by])


class FoundationNote(Base):
    """A team's research note on a foundation, shown in the main table.

    One note per (team, foundation), shared like folders: prospect research
    is a team activity, and a note only its author can see is a note the
    team will re-discover the hard way. Distinct from FolderItem.note, which
    annotates a save inside one folder — this annotates the foundation
    itself, saved or not, which is how it can appear as a table column while
    browsing.

    Scale posture: every read is one indexed per-team query, the payload is
    bounded by a team's own typing, and nothing here needs to change as
    teams are added — team_id scoping is the whole model.
    """

    __tablename__ = "foundation_notes"
    __table_args__ = (
        # The upsert target: PUT /notes/{ein} is ON CONFLICT DO UPDATE, so a
        # teammate saving concurrently last-writes rather than erroring.
        UniqueConstraint("team_id", "ein", name="uq_foundation_notes_team_ein"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    # Same non-FK stance as FolderItem.ein, same reason.
    ein: Mapped[str] = mapped_column(String(9), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False)

    editor: Mapped[User | None] = relationship(foreign_keys=[updated_by])
