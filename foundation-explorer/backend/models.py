"""Query-parameter models shared by routes."""

from fastapi import Query
from pydantic import BaseModel


class FoundationFilters(BaseModel):
    q: str | None = None
    states: list[str] = []
    score_min: float | None = None
    score_max: float | None = None
    pct_min: float | None = None
    christian_min: float | None = None
    status: list[str] = []
    sizes: list[str] = []
    has_filings: bool = False
    has_contact: bool = False
    has_website: bool = False
    has_phone: bool = False
    has_deadline: bool = False
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
    score_min: float | None = None,
    score_max: float | None = None,
    pct_min: float | None = None,
    christian_min: float | None = None,
    status: list[str] = Query(default=[]),
    sizes: list[str] = Query(default=[]),
    has_filings: bool = False,
    has_contact: bool = False,
    has_website: bool = False,
    has_phone: bool = False,
    has_deadline: bool = False,
    include_trusts: bool = False,
    include_small: bool = False,
    preset: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
) -> FoundationFilters:
    return FoundationFilters(
        q=q, states=states, score_min=score_min, score_max=score_max,
        pct_min=pct_min, christian_min=christian_min, status=status,
        sizes=sizes, has_filings=has_filings, has_contact=has_contact,
        has_website=has_website, has_phone=has_phone,
        has_deadline=has_deadline, include_trusts=include_trusts,
        include_small=include_small, preset=preset, sort=sort,
        direction=direction, page=max(1, page), page_size=page_size,
    )
