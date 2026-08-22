"""Unified search over foundations, recipients, missions and grant purposes.

One box, four sources, one ranked list of foundations. A fundraiser does not
know in advance whether the thing they remember is a funder's name, a grantee's
name, or a phrase from a mission statement, and making them choose a field
first is making them guess.

Ranked with BM25 (SQLite FTS5's built-in Okapi BM25), tiered so that a match on
the foundation's own name always outranks a match reached indirectly through a
grantee. Someone typing "Lilly" wants Lilly Endowment, not the two hundred
foundations that gave to a grantee with "lilly" in its mission.

Every result carries the evidence for why it is there -- which field matched,
and a highlighted snippet of the matching text -- because a search result a
user cannot explain is one they cannot trust. That is the same principle the
read model applies to its coverage numbers.

The index is built by src/build_search_index.py and lives in the same SQLite
file. This module is read-only, like the rest of the v5 read path.
"""

from __future__ import annotations

import re
import time

import v5
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v5", tags=["search"])

# Tier weights. The gaps are large on purpose: they are ordering guarantees,
# not nudges. Any name match must beat any recipient match, whatever BM25 says
# about the individual scores, so the gap has to exceed the plausible range of
# the relevance term added within a tier.
TIER = {
    "name": 10_000.0,
    "location": 3_000.0,
    "recipient": 1_000.0,
    "mission": 400.0,
    "purpose": 150.0,
}

# Additional hits in a field the foundation already matched. Deliberately
# tiny: the arithmetic below has to hold no matter how many hits arrive.
#
#   best possible score without a name match
#     = 3000 + 1000 + 400 + 150   (every other tier)
#     + 4 x 100                   (relevance is clamped to 100 by _rel)
#     + 4 x 25 x EXTRA_HIT_BONUS  (extras, capped per field)
#     = 5050  <  10000            (any name match at all)
#
# So a name match always sorts first, which is the guarantee the product asks
# for, and it survives any distribution of hits rather than holding by luck.
EXTRA_HIT_BONUS = 0.5
EXTRA_HIT_CAP = 25

# Fan-out is scaled to what the caller asked for. Typeahead wants 20 results
# and should stay under a keystroke; the results table wants 100 and can
# afford to look wider. A fixed large value would make every keystroke pay for
# the table's depth. Both are bounded so a one-letter query cannot drag the
# whole index into memory.
def _fan_out(limit: int) -> tuple[int, int]:
    """(rows per FTS table, cap on funder<-grantee edges)."""
    fts = min(800, max(200, limit * 6))
    edges = min(2400, max(600, limit * 18))
    return fts, edges

MAX_QUERY_CHARS = 200
SNIPPET_TOKENS = 14

# FTS5 treats these as syntax. A user typing them means them literally, so
# they are stripped rather than escaped -- there is no sensible query language
# to expose in a single search box.
_FTS_SYNTAX = re.compile(r'[":^*(){}\[\]]')
_TOKEN = re.compile(r"[0-9A-Za-zÀ-ɏ]+")


class MatchOut(BaseModel):
    field: str
    label: str
    snippet: str
    # Names the specific entity behind an indirect match, e.g. which grantee.
    detail: str | None = None


class ResultOut(BaseModel):
    ein: str
    name: str
    city: str | None
    state: str | None
    paid_2324: float
    christian_dollars: float
    pct_christian: float | None
    coverage_band: str | None
    application_status: str | None
    score: float
    matches: list[MatchOut]


class SearchOut(BaseModel):
    query: str
    took_ms: float
    count: int
    results: list[ResultOut]


def build_match(raw: str) -> tuple[str, bool]:
    """Turn user text into an FTS5 MATCH expression.

    Returns (expression, is_prefix). Each token becomes a quoted phrase so
    nothing the user types can be read as FTS5 syntax, and the final token
    gets a prefix wildcard so results appear while they are still typing.
    """
    tokens = _TOKEN.findall(_FTS_SYNTAX.sub(" ", raw))
    if not tokens:
        return "", False
    quoted = [f'"{t}"' for t in tokens[:-1]]
    last = tokens[-1]
    # A one- or two-character final token as a prefix matches an enormous
    # slice of the index for no benefit, so only extend from three characters.
    if len(last) >= 3:
        quoted.append(f'"{last}"*')
        prefix = True
    else:
        quoted.append(f'"{last}"')
        prefix = False
    return " AND ".join(quoted), prefix


def _looks_like_ein(raw: str) -> str | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 9 and not any(ch.isalpha() for ch in raw):
        return digits
    return None


class _Acc:
    """Accumulates per-foundation score and evidence across the four sources."""

    def __init__(self) -> None:
        self.score = 0.0
        self.matches: dict[str, MatchOut] = {}
        self.extra: dict[str, int] = {}

    def add(self, field: str, label: str, relevance: float, snippet: str,
            detail: str | None = None) -> None:
        if field in self.matches:
            # A tier is earned once per field, never once per hit. Paying it
            # per hit let a foundation with two dozen matching grantees score
            # 24,000 and outrank an exact name match -- the one ordering this
            # search is required to guarantee. Repeats are worth something,
            # but only a rounding error against the tier gaps.
            seen = self.extra.get(field, 0) + 1
            self.extra[field] = seen
            if seen <= EXTRA_HIT_CAP:
                self.score += EXTRA_HIT_BONUS
            return
        self.score += TIER[field] + relevance
        self.matches[field] = MatchOut(field=field, label=label,
                                       snippet=snippet.strip(), detail=detail)

    def finish(self) -> list[MatchOut]:
        ordered = sorted(self.matches.values(), key=lambda m: -TIER[m.field])
        for match in ordered:
            # When the grantee's name IS the matched text, the detail repeats
            # the snippet verbatim. Drop it rather than render the same words
            # twice side by side.
            if match.detail and _strip_tags(match.snippet) == match.detail:
                match.detail = None
            more = self.extra.get(match.field, 0)
            if more:
                noun = {"recipient": "recipient", "mission": "mission",
                        "purpose": "purpose"}.get(match.field, "match")
                match.detail = (
                    f"{match.detail} +{more} more" if match.detail
                    else f"and {more} more {noun}{'s' if more != 1 else ''}")
        # Escape last: everything above compares plain text, and the only
        # markup that survives is the <b> this puts in.
        for match in ordered:
            match.snippet = _to_html(match.snippet)
        return ordered


# SQLite's snippet() wraps hits in whatever delimiters it is given and does no
# escaping of the surrounding text. Handing it "<b>" directly would splice raw
# 990-PF filing text into the DOM: 48,353 indexed rows contain "<" or "&"
# already ("CONTRIBUTIONS <= 1,000" and similar), and the source is third-party
# data we do not control. So snippets are marked with sentinels, escaped, and
# only then given their tags -- the only markup in the output is markup we put
# there.
MARK_OPEN = "\x02"
MARK_CLOSE = "\x03"


def _to_html(marked: str) -> str:
    escaped = (marked.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace('"', "&quot;"))
    return (escaped.replace(MARK_OPEN, "<b>")
                   .replace(MARK_CLOSE, "</b>"))


def _hit(marked: str | None) -> bool:
    return bool(marked) and MARK_OPEN in marked


def _strip_tags(text: str) -> str:
    """Plain text of a marked snippet, for comparing against a detail label."""
    return text.replace(MARK_OPEN, "").replace(MARK_CLOSE, "").strip()


def _rel(bm25_value: float) -> float:
    """BM25 in FTS5 is negative, better matches more negative.

    Flip the sign and squash into roughly 0..100 so a pathological score can
    never climb into the next tier's band.
    """
    return min(100.0, max(0.0, -bm25_value * 5.0))


@router.get("/search", response_model=SearchOut)
def search(
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_CHARS),
    limit: int = Query(20, ge=1, le=200),
) -> SearchOut:
    started = time.perf_counter()
    conn = v5.connect()
    try:
        acc: dict[str, _Acc] = {}

        # An EIN is an exact identifier, not a search term. Short-circuit so
        # that pasting one from a filing goes straight to the foundation.
        ein = _looks_like_ein(q)
        if ein:
            row = conn.execute(
                "SELECT ein, name FROM foundations WHERE ein = ?", (ein,)
            ).fetchone()
            if row:
                entry = acc.setdefault(row["ein"], _Acc())
                entry.add("name", "EIN", 100.0, row["name"] or "",
                          f"EIN {ein}")

        expr, _ = build_match(q)
        if not expr and not acc:
            raise HTTPException(
                status_code=400,
                detail="Enter at least one letter or digit to search.")

        if expr:
            fts, edge_cap = _fan_out(limit)
            _foundations(conn, expr, acc, fts)
            _recipients(conn, expr, acc, fts, edge_cap)
            _purposes(conn, expr, acc, fts)

        if not acc:
            return SearchOut(query=q, count=0, results=[],
                             took_ms=round((time.perf_counter() - started) * 1000, 1))

        ranked = sorted(acc.items(), key=lambda kv: -kv[1].score)[:limit]
        results = _hydrate(conn, ranked)
        return SearchOut(
            query=q, count=len(results), results=results,
            took_ms=round((time.perf_counter() - started) * 1000, 1))
    finally:
        conn.close()


def _foundations(conn, expr: str, acc: dict[str, _Acc], fts: int) -> None:
    rows = conn.execute(f"""
        SELECT ein,
               bm25(search_foundation, 12.0, 3.0) AS rank,
               snippet(search_foundation, 1, char(2), char(3), '', {SNIPPET_TOKENS}) AS name_hit,
               snippet(search_foundation, 2, char(2), char(3), '', {SNIPPET_TOKENS}) AS loc_hit
        FROM search_foundation
        WHERE search_foundation MATCH ?
        ORDER BY rank
        LIMIT {fts}
    """, (expr,)).fetchall()
    for row in rows:
        entry = acc.setdefault(row["ein"], _Acc())
        # An empty snippet means that column did not contribute the match.
        if row["name_hit"] and _hit(row["name_hit"]):
            entry.add("name", "Foundation name", _rel(row["rank"]),
                      row["name_hit"])
        elif row["loc_hit"] and _hit(row["loc_hit"]):
            entry.add("location", "Location", _rel(row["rank"]), row["loc_hit"])


def _recipient_rows(conn, expr: str, column: str, limit: int):
    """Top grantees matching within one column.

    Queried per column rather than once across both. A single query ranks
    name and mission together, and since names are weighted higher and are
    far shorter, name matches take almost every slot: "gospel" returned 69
    grantee-name matches and zero mission matches, so the mission column was
    empty for exactly the queries it existed to serve. Giving each column its
    own budget guarantees both routes are represented.
    """
    return conn.execute(f"""
        SELECT entity_id,
               bm25(search_recipient, 8.0, 2.0) AS rank,
               name,
               snippet(search_recipient, 1, char(2), char(3), '…', {SNIPPET_TOKENS}) AS name_hit,
               snippet(search_recipient, 2, char(2), char(3), '…', {SNIPPET_TOKENS}) AS mission_hit
        FROM search_recipient
        WHERE search_recipient MATCH ?
        ORDER BY rank
        LIMIT {limit}
    """, (f"{{{column}}} : ({expr})",)).fetchall()


def _recipients(conn, expr: str, acc: dict[str, _Acc], fts: int,
                edge_cap: int) -> None:
    half = max(60, fts // 2)
    rows = [*_recipient_rows(conn, expr, "name", half),
            *_recipient_rows(conn, expr, "mission", half)]
    if not rows:
        return

    # A grantee whose name and mission both match appears in both result
    # sets; keep the better-ranked row (bm25 is negative, so lower is better).
    by_entity: dict[str, object] = {}
    for row in rows:
        best = by_entity.get(row["entity_id"])
        if best is None or row["rank"] < best["rank"]:
            by_entity[row["entity_id"]] = row
    placeholders = ",".join("?" for _ in by_entity)
    # search_edge is the precomputed funder<-grantee rollup, so this is an
    # indexed scan rather than a GROUP BY over 3M grant rows. Ordered by
    # dollars so that when the cap bites it keeps the funding relationships
    # that actually matter rather than an arbitrary slice.
    edges = conn.execute(f"""
        SELECT funder_ein, entity_id
        FROM search_edge
        WHERE entity_id IN ({placeholders})
        ORDER BY dollars DESC
        LIMIT {edge_cap}
    """, tuple(by_entity)).fetchall()

    for edge in edges:
        row = by_entity.get(edge["entity_id"])
        if row is None:
            continue
        entry = acc.setdefault(edge["funder_ein"], _Acc())
        who = (row["name"] or "").strip() or None
        if row["name_hit"] and _hit(row["name_hit"]):
            entry.add("recipient", "Grantee name", _rel(row["rank"]),
                      row["name_hit"], who)
        elif row["mission_hit"] and _hit(row["mission_hit"]):
            entry.add("mission", "Grantee mission", _rel(row["rank"]),
                      row["mission_hit"], who)


def _purposes(conn, expr: str, acc: dict[str, _Acc], fts: int) -> None:
    rows = conn.execute(f"""
        SELECT ein,
               bm25(search_purpose) AS rank,
               snippet(search_purpose, 1, char(2), char(3), '…', {SNIPPET_TOKENS}) AS hit
        FROM search_purpose
        WHERE search_purpose MATCH ?
        ORDER BY rank
        LIMIT {fts}
    """, (expr,)).fetchall()
    for row in rows:
        entry = acc.setdefault(row["ein"], _Acc())
        if row["hit"] and _hit(row["hit"]):
            entry.add("purpose", "Grant purpose", _rel(row["rank"]), row["hit"])


def _hydrate(conn, ranked: list[tuple[str, _Acc]]) -> list[ResultOut]:
    """Attach the display columns, preserving the ranked order."""
    eins = [ein for ein, _ in ranked]
    placeholders = ",".join("?" for _ in eins)
    rows = {
        r["ein"]: r for r in conn.execute(f"""
            SELECT ein, name, city, state, paid_2324, christian_dollars,
                   pct_christian, coverage_band, application_status
            FROM foundations WHERE ein IN ({placeholders})
        """, tuple(eins)).fetchall()
    }
    out: list[ResultOut] = []
    for ein, entry in ranked:
        row = rows.get(ein)
        if row is None:
            # An index entry with no foundation behind it means the search
            # index is stale relative to the read model. Skip rather than
            # invent a row; rebuilding the index fixes it.
            continue
        out.append(ResultOut(
            ein=row["ein"], name=row["name"] or "",
            city=row["city"], state=row["state"],
            paid_2324=row["paid_2324"] or 0,
            christian_dollars=row["christian_dollars"] or 0,
            pct_christian=row["pct_christian"],
            coverage_band=row["coverage_band"],
            application_status=row["application_status"],
            score=round(entry.score, 2), matches=entry.finish(),
        ))
    return out
