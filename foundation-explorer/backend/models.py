"""Query-parameter models shared by routes."""

from fastapi import Query
from pydantic import BaseModel


class FoundationFilters(BaseModel):
    q: str | None = None
    states: list[str] = []
    verdict: str | None = None            # strong (default) | some | any
    christian_min: float | None = None
    recently_active: bool = False
    sizes: list[str] = []
    has_contact: bool = False
    has_website: bool = False
    has_phone: bool = False
    include_invite: bool = False
    include_trusts: bool = False
    include_small: bool = False
    preset: str | None = None
    sort: str | None = None
    direction: str | None = None
    page: int = 1
    page_size: int = 50


def foundation_filters_dep(
    q: str | None = None,
    states: list[str] = Query(default=[]),
    verdict: str | None = None,
    christian_min: float | None = None,
    recently_active: bool = False,
    sizes: list[str] = Query(default=[]),
    has_contact: bool = False,
    has_website: bool = False,
    has_phone: bool = False,
    include_invite: bool = False,
    include_trusts: bool = False,
    include_small: bool = False,
    preset: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
) -> FoundationFilters:
    return FoundationFilters(
        q=q, states=states, verdict=verdict, christian_min=christian_min,
        recently_active=recently_active, sizes=sizes, has_contact=has_contact,
        has_website=has_website, has_phone=has_phone,
        include_invite=include_invite, include_trusts=include_trusts,
        include_small=include_small, preset=preset, sort=sort,
        direction=direction, page=max(1, page), page_size=page_size,
    )
