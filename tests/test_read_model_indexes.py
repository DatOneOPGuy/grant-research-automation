"""Indexes the read model needs to stay fast.

Each of these was added after an endpoint was measured being slow without
it, and each lives in a build script rather than only in whoever's database
happened to get an ad-hoc CREATE INDEX. A missing index does not fail
anything -- it just makes a page take eleven seconds, which is the kind of
regression that ships.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "explorer_v5.db"

# index name -> why it exists, quoted in the failure message
REQUIRED = {
    "idx_g_amount": "the grants explorer pages by amount; 11.5s -> 53ms",
    "idx_g_funder": "per-foundation grant lookups",
    "idx_g_entity": "recipient -> funder joins, used by search and sectors",
}


def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


@pytest.mark.parametrize("name,reason", sorted(REQUIRED.items()))
def test_required_index_exists(name, reason):
    conn = _conn()
    found = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?",
        (name,)).fetchone()[0]
    conn.close()
    assert found == 1, f"{name} is missing -- {reason}"


@pytest.mark.parametrize("name", sorted(REQUIRED))
def test_required_index_is_in_a_build_script(name):
    """An index only in someone's local database is a regression waiting."""
    scripts = list((ROOT / "src").glob("build_*.py"))
    assert any(name in s.read_text() for s in scripts), (
        f"{name} exists in the database but no build_*.py creates it, so the "
        "next rebuild would drop it")
