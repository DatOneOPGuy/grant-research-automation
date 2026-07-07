"""Query-parameter models shared by routes."""

from fastapi import Query
from pydantic import BaseModel


class FoundationFilters(BaseModel):
    q: str | None = None
    # Christian-giving depth
    min_orgs: int | None = None
    christian_min: float | None = None
    recently_active: bool = False
    traditions: list[str] = []
    # grant-size behavior
    typical_sizes: list[str] = []
    largest_min: float | None = None
    # reachability
    include_invite: bool = False
    status: list[str] = []
    has_contact: bool = False
    has_website: bool = False
    has_phone: bool = False
    has_deadline: bool = False
    # geography
    states: list[str] = []
    region: str | None = None
    gives_in_state: str | None = None
    # foundation profile
    sizes: list[str] = []
    asset_buckets: list[str] = []
    actively_giving: bool = False
    include_trusts: bool = False
    include_small: bool = False
    # meta
    preset: str | None = None
    sort: str | None = None
    direction: str | None = None
    page: int = 1
    page_size: int = 50


def foundation_filters_dep(
    q: str | None = None,
    min_orgs: int | None = None,
    christian_min: float | None = None,
    recently_active: bool = False,
    traditions: list[str] = Query(default=[]),
    typical_sizes: list[str] = Query(default=[]),
    largest_min: float | None = None,
    include_invite: bool = False,
    status: list[str] = Query(default=[]),
    has_contact: bool = False,
    has_website: bool = False,
    has_phone: bool = False,
    has_deadline: bool = False,
    states: list[str] = Query(default=[]),
    region: str | None = None,
    gives_in_state: str | None = None,
    sizes: list[str] = Query(default=[]),
    asset_buckets: list[str] = Query(default=[]),
    actively_giving: bool = False,
    include_trusts: bool = False,
    include_small: bool = False,
    preset: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
) -> FoundationFilters:
    return FoundationFilters(
        q=q, min_orgs=min_orgs, christian_min=christian_min,
        recently_active=recently_active, traditions=traditions,
        typical_sizes=typical_sizes, largest_min=largest_min,
        include_invite=include_invite, status=status, has_contact=has_contact,
        has_website=has_website, has_phone=has_phone, has_deadline=has_deadline,
        states=states, region=region, gives_in_state=gives_in_state,
        sizes=sizes, asset_buckets=asset_buckets,
        actively_giving=actively_giving, include_trusts=include_trusts,
        include_small=include_small, preset=preset, sort=sort,
        direction=direction, page=max(1, page), page_size=page_size,
    )
