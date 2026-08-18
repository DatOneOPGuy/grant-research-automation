"""Shared saved folders: the product's only write surface.

Mounted alongside v5.router, which stays read-only and untouched.

Every query in this module filters on the caller's team_id. That is the whole
authorisation model, so it lives in one helper rather than being repeated at
each endpoint -- an isolation rule copied seven times is an isolation rule
that will eventually be copied six times.
"""

from __future__ import annotations

from datetime import datetime

from auth import current_user
from db_session import get_db
from fastapi import APIRouter, Depends, HTTPException
from models_db import Folder, FolderItem, User
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

router = APIRouter(prefix="/api/v5", tags=["accounts"])


# --- wire shapes -------------------------------------------------------------

class ItemOut(BaseModel):
    ein: str
    note: str | None
    added_by: str | None
    created_at: datetime


class FolderOut(BaseModel):
    id: int
    name: str
    created_by: str | None
    created_at: datetime
    # Folders arrive with their contents. The client derives its entire saved
    # surface -- is-saved, folders-for-EIN, EINs-in-folder -- from this one
    # response, so splitting it would turn every page load into an N+1 to
    # rebuild state it always needs in full.
    items: list[ItemOut]


class MeOut(BaseModel):
    email: str
    team_id: int
    team_name: str
    created_at: datetime


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("name cannot be blank")
        return clean


class ItemIn(BaseModel):
    ein: str = Field(min_length=1, max_length=11)
    note: str | None = None

    @field_validator("ein")
    @classmethod
    def _digits(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) != 9:
            raise ValueError("ein must be 9 digits")
        return digits


# --- helpers -----------------------------------------------------------------

def _email(user: User | None) -> str | None:
    return user.email if user else None


def _serialise(folder: Folder) -> FolderOut:
    return FolderOut(
        id=folder.id, name=folder.name, created_by=_email(folder.creator),
        created_at=folder.created_at,
        items=[
            ItemOut(ein=i.ein, note=i.note, added_by=_email(i.adder),
                    created_at=i.created_at)
            for i in sorted(folder.items, key=lambda i: i.created_at)
        ],
    )


def _folder_for(db: Session, user: User, folder_id: int) -> Folder:
    """The caller's folder, or 404.

    404 and not 403 for a folder belonging to another team. A 403 confirms the
    id exists, which hands an attacker a way to enumerate other teams' folders
    one integer at a time; a 404 says only that this caller has no such
    folder, which is true either way.
    """
    folder = db.scalars(
        select(Folder)
        .options(selectinload(Folder.items).selectinload(FolderItem.adder),
                 selectinload(Folder.creator))
        .where(Folder.id == folder_id, Folder.team_id == user.team_id)
    ).first()
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


# --- endpoints ---------------------------------------------------------------

@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)) -> MeOut:
    return MeOut(email=user.email, team_id=user.team_id,
                 team_name=user.team.name, created_at=user.created_at)


@router.get("/folders", response_model=list[FolderOut])
def list_folders(
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> list[FolderOut]:
    folders = db.scalars(
        select(Folder)
        .options(selectinload(Folder.items).selectinload(FolderItem.adder),
                 selectinload(Folder.creator))
        .where(Folder.team_id == user.team_id)
        .order_by(Folder.created_at, Folder.id)
    ).all()
    return [_serialise(f) for f in folders]


@router.post("/folders", response_model=FolderOut, status_code=201)
def create_folder(
    body: FolderIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderOut:
    """Create a folder, or return the existing one with that name.

    Case-insensitively unique per team. Two people creating "Q1 asks" a minute
    apart is an ordinary Tuesday on a shared list, and merging them silently is
    better than either an error the second person cannot act on or two folders
    the team has to reconcile by hand.
    """
    existing = db.scalars(
        select(Folder)
        .options(selectinload(Folder.items).selectinload(FolderItem.adder),
                 selectinload(Folder.creator))
        .where(Folder.team_id == user.team_id,
               func.lower(Folder.name) == body.name.lower())
    ).first()
    if existing is not None:
        return _serialise(existing)

    folder = Folder(team_id=user.team_id, name=body.name, created_by=user.id)
    db.add(folder)
    try:
        db.commit()
    except Exception:
        # Lost a race against a concurrent create of the same name.
        db.rollback()
        return _serialise(_by_name(db, user, body.name))
    db.refresh(folder)
    return _serialise(folder)


def _by_name(db: Session, user: User, name: str) -> Folder:
    folder = db.scalars(
        select(Folder)
        .options(selectinload(Folder.items).selectinload(FolderItem.adder),
                 selectinload(Folder.creator))
        .where(Folder.team_id == user.team_id,
               func.lower(Folder.name) == name.lower())
    ).first()
    if folder is None:
        raise HTTPException(status_code=409, detail="Could not create folder")
    return folder


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def rename_folder(
    folder_id: int, body: FolderIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderOut:
    folder = _folder_for(db, user, folder_id)
    clash = db.scalars(
        select(Folder.id).where(
            Folder.team_id == user.team_id,
            func.lower(Folder.name) == body.name.lower(),
            Folder.id != folder.id)
    ).first()
    if clash is not None:
        raise HTTPException(
            status_code=409,
            detail=f'Another folder is already named "{body.name}".')
    folder.name = body.name
    db.commit()
    db.refresh(folder)
    return _serialise(folder)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(
    folder_id: int, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    folder = _folder_for(db, user, folder_id)
    db.delete(folder)  # items cascade
    db.commit()


@router.post("/folders/{folder_id}/items", response_model=FolderOut,
             status_code=201)
def add_item(
    folder_id: int, body: ItemIn, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderOut:
    """Add a foundation to a folder. Idempotent.

    ON CONFLICT DO NOTHING against UNIQUE(folder_id, ein): a double-click, a
    retry, or a teammate saving the same foundation at the same moment is a
    no-op, not a 500. The note on an existing row is left alone -- an add is
    not an edit, and overwriting someone else's note would be a silent loss.
    """
    folder = _folder_for(db, user, folder_id)
    db.execute(
        pg_insert(FolderItem)
        .values(folder_id=folder.id, ein=body.ein, note=body.note,
                added_by=user.id)
        .on_conflict_do_nothing(constraint="uq_folder_items_folder_ein")
    )
    db.commit()
    return _serialise(_folder_for(db, user, folder_id))


@router.delete("/folders/{folder_id}/items/{ein}", status_code=204)
def remove_item(
    folder_id: int, ein: str, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove one foundation from one folder. Idempotent: absent is success."""
    folder = _folder_for(db, user, folder_id)
    db.execute(delete(FolderItem).where(
        FolderItem.folder_id == folder.id, FolderItem.ein == ein))
    db.commit()


@router.delete("/items/{ein}", status_code=204)
def remove_item_everywhere(
    ein: str, user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """Unsave a foundation across every folder in the team.

    One transaction rather than the client issuing a delete per folder: a
    fan-out that half-fails leaves the foundation saved in some folders and
    not others, and the user has no way to see which.
    """
    folder_ids = select(Folder.id).where(Folder.team_id == user.team_id)
    db.execute(delete(FolderItem).where(
        FolderItem.ein == ein, FolderItem.folder_id.in_(folder_ids)))
    db.commit()
