"""The API's default sort must equal the frontend's.

v5FilterParams deliberately omits `sort` from the query string when it equals
defaultV5Filters.sort, so shared URLs stay short. That makes the two defaults
a single value split across two languages: if they disagree, the client
believes it asked for one ordering and the server quietly applies another,
with no error anywhere.

It happened. The frontend default moved to 'christian' -- biggest Christian
funders first -- while v5.py still said 'paid', so the flagship table opened
sorted by total giving with a descending arrow drawn over the Christian $
column it was not sorted by.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "foundation-explorer" / "backend" / "v5.py"
FRONTEND = ROOT / "foundation-explorer" / "frontend" / "src" / "lib" / "apiV5.ts"


def _backend_default() -> str:
    m = re.search(r'^\s*sort: str = "([a-z_]+)"', BACKEND.read_text(), re.M)
    assert m, "could not find the sort default in v5.py"
    return m.group(1)


def _frontend_default(field: str) -> str:
    text = FRONTEND.read_text()
    block = re.search(r"export const defaultV5Filters[^{]*\{(.*?)\n\}",
                      text, re.S)
    assert block, "could not find defaultV5Filters in apiV5.ts"
    m = re.search(rf"^\s*{field}:\s*'([a-z_]+)'", block.group(1), re.M)
    assert m, f"could not find {field} in defaultV5Filters"
    return m.group(1)


@pytest.mark.skipif(not BACKEND.exists() or not FRONTEND.exists(),
                    reason="explorer sources not present")
def test_default_sort_agrees_across_the_api_boundary():
    assert _backend_default() == _frontend_default("sort"), (
        f"v5.py sorts by {_backend_default()!r} by default but the frontend "
        f"believes the default is {_frontend_default('sort')!r}, and omits "
        "the parameter when it matches -- so the table would silently render "
        "in the wrong order")


@pytest.mark.skipif(not FRONTEND.exists(), reason="frontend not present")
def test_the_static_adapter_uses_the_same_default():
    """The demo build filters client-side and must not disagree either."""
    text = FRONTEND.read_text()
    m = re.search(r"const sortKey = p\.get\('sort'\) \|\| '([a-z_]+)'", text)
    assert m, "could not find the static adapter's sort fallback"
    assert m.group(1) == _frontend_default("sort")
