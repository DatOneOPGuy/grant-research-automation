"""Unified search: ranking guarantees, query safety and output safety.

Runs against the real read model, because the things worth testing here are
properties of real data: that a name match outranks a match reached through a
grantee's mission, and that filing text containing "<" cannot become markup.
Skips when explorer_v5.db has no search index, so a checkout without one is
not a failure.

    python3 -m src.build_search_index
    pytest tests/test_search.py
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "foundation-explorer" / "backend"
DB = Path(__file__).resolve().parents[1] / "data" / "explorer_v5.db"

if not DB.exists():
    pytest.skip("explorer_v5.db not present", allow_module_level=True)

_conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
_has_index = _conn.execute(
    "SELECT count(*) FROM sqlite_master WHERE type='table' "
    "AND name IN ('search_foundation','search_recipient','search_purpose',"
    "'search_edge')").fetchone()[0]
_conn.close()
if _has_index < 4:
    pytest.skip("search index not built (run src.build_search_index)",
                allow_module_level=True)

sys.path.insert(0, str(BACKEND))
search = pytest.importorskip("search")


def run(q: str, limit: int = 20):
    return search.search(q=q, limit=limit)


# --- query construction ------------------------------------------------------

@pytest.mark.parametrize("raw", [
    '"', "*", "((", "))", "^", "NOT", "AND OR", "a*b", "foo:bar", "[x]",
    "'; DROP TABLE foundations; --", "\\", "{}",
])
def test_hostile_queries_never_raise_fts_syntax_errors(raw):
    """Whatever the user types is data, not query syntax.

    FTS5 has its own expression language; letting a stray quote or paren reach
    it turns a search box into a source of 500s.
    """
    try:
        run(raw, limit=3)
    except Exception as exc:  # noqa: BLE001 - the point is that none escape
        from fastapi import HTTPException
        # A 400 for "nothing searchable here" is a valid answer; anything
        # else means the expression reached SQLite malformed.
        assert isinstance(exc, HTTPException) and exc.status_code == 400, exc


def test_tokens_are_quoted_so_operators_are_literal():
    """"AND" typed by a user is a word to search for, not an operator.

    Case is preserved -- FTS5 phrase matching is case-insensitive, so there is
    nothing to gain by folding it here -- but the quoting is what stops the
    token being parsed as syntax.
    """
    expr, _ = search.build_match("gospel AND orphan")
    assert expr == '"gospel" AND "AND" AND "orphan"*'


def test_short_final_token_is_not_prefixed():
    """A one- or two-letter prefix matches most of the index for no benefit."""
    _, prefix = search.build_match("ab")
    assert prefix is False
    _, prefix = search.build_match("abc")
    assert prefix is True


# --- the ranking guarantee ---------------------------------------------------

def test_foundation_name_matches_rank_above_indirect_matches():
    """The product's stated ordering rule, checked on real data.

    An earlier version paid the tier weight per hit rather than per field, so
    a foundation with two dozen matching grantees scored 24,000 and buried the
    exact name match. This is that regression.
    """
    out = run("christian", limit=25)
    fields = [r.matches[0].field for r in out.results]
    # Every name match must precede the first non-name match.
    first_indirect = next(
        (i for i, f in enumerate(fields) if f != "name"), len(fields))
    assert "name" not in fields[first_indirect:], (
        f"an indirect match outranked a name match: {fields}")


def test_many_grantee_hits_cannot_outscore_one_name_match():
    """Score arithmetic, not data: the tier gap must be unreachable."""
    acc = search._Acc()
    for i in range(500):
        acc.add("recipient", "Grantee name", 100.0, f"hit {i}", None)
        acc.add("mission", "Grantee mission", 100.0, f"m {i}", None)
        acc.add("purpose", "Grant purpose", 100.0, f"p {i}", None)
    acc.add("location", "Location", 100.0, "loc")
    name_only = search._Acc()
    name_only.add("name", "Foundation name", 0.0, "x")
    assert acc.score < name_only.score, (
        f"{acc.score} >= {name_only.score}: a pile of indirect hits "
        "outranked a bare name match")


def test_results_are_returned_in_descending_score_order():
    out = run("youth", limit=20)
    scores = [r.score for r in out.results]
    assert scores == sorted(scores, reverse=True)


# --- attribution -------------------------------------------------------------

def test_every_result_explains_itself():
    for query in ("prison ministry", "orphan", "seminary"):
        out = run(query, limit=10)
        for r in out.results:
            assert r.matches, f"{r.name} has no match evidence for {query!r}"
            for m in r.matches:
                assert m.field in search.TIER
                assert m.snippet


def test_indirect_matches_name_the_grantee_behind_them():
    out = run("young life", limit=20)
    indirect = [m for r in out.results for m in r.matches
                if m.field in ("recipient", "mission")]
    assert indirect, "expected at least one grantee-mediated match"
    # Either the snippet is the grantee name itself, or detail names it.
    assert any(m.detail for m in indirect)


# --- output safety -----------------------------------------------------------

_ALLOWED = re.compile(r"</?b>")
_ENTITY = re.compile(r"&(?!amp;|lt;|gt;|quot;|#\d+;)")


def test_snippets_contain_no_markup_beyond_our_own_bold():
    """990-PF text is third-party data and the client renders these as HTML.

    48,000+ indexed rows already contain "<" or "&" ("CONTRIBUTIONS <= 1,000"),
    and SQLite's snippet() does no escaping of its own.
    """
    for query in ("contributions", "christian", "support", "fund"):
        out = run(query, limit=25)
        for r in out.results:
            for m in r.matches:
                bare = _ALLOWED.sub("", m.snippet)
                assert "<" not in bare, f"unescaped '<' in {m.snippet!r}"
                assert ">" not in bare, f"unescaped '>' in {m.snippet!r}"
                assert not _ENTITY.search(bare), f"raw '&' in {m.snippet!r}"


def test_escaping_is_applied_after_marking():
    marked = f"a {search.MARK_OPEN}<b>{search.MARK_CLOSE} & \"q\""
    assert search._to_html(marked) == 'a <b>&lt;b&gt;</b> &amp; &quot;q&quot;'


def test_bold_tags_are_balanced():
    out = run("christian foundation", limit=20)
    for r in out.results:
        for m in r.matches:
            assert m.snippet.count("<b>") == m.snippet.count("</b>")


# --- shape -------------------------------------------------------------------

def test_an_ein_goes_straight_to_its_foundation():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ein = conn.execute(
        "SELECT ein FROM foundations WHERE paid_2324 > 0 LIMIT 1").fetchone()[0]
    conn.close()
    out = run(ein, limit=5)
    assert out.results and out.results[0].ein == ein
    # Also with the hyphenated form people paste from filings.
    hyphenated = f"{ein[:2]}-{ein[2:]}"
    assert run(hyphenated, limit=5).results[0].ein == ein


def test_no_matches_is_an_empty_list_not_an_error():
    out = run("zzzzqqqxyzzz", limit=5)
    assert out.count == 0
    assert out.results == []


def test_limit_is_respected():
    assert len(run("foundation", limit=5).results) <= 5
