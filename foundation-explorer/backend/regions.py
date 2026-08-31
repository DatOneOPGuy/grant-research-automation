"""Census regions and divisions.

Two levels of geography above the state, both derived rather than filed:

**Regions** are the four Census regions and nine divisions, a pure mapping
over the state code. No new data, no coverage loss -- if a grant has a state
it has a region.

Lives here rather than in src/ because only the API needs it, and the
backend runs as a flat module directory with no path to the pipeline
package. The city-to-county crosswalk it was originally written beside is
the mirror case -- only the builder needs that -- so the two were split.
"""

from __future__ import annotations

# --- regions ----------------------------------------------------------------

# Census divisions, and the region each belongs to. Standard definitions, so
# "Northeast" means what a reader expects rather than something we invented.
DIVISIONS: dict[str, tuple[str, str]] = {}


def _add(region: str, division: str, states: str) -> None:
    for code in states.split():
        DIVISIONS[code] = (region, division)


_add("Northeast", "New England", "CT ME MA NH RI VT")
_add("Northeast", "Mid-Atlantic", "NJ NY PA")
_add("Midwest", "East North Central", "IL IN MI OH WI")
_add("Midwest", "West North Central", "IA KS MN MO NE ND SD")
_add("South", "South Atlantic", "DE DC FL GA MD NC SC VA WV")
_add("South", "East South Central", "AL KY MS TN")
_add("South", "West South Central", "AR LA OK TX")
_add("West", "Mountain", "AZ CO ID MT NV NM UT WY")
_add("West", "Pacific", "AK CA HI OR WA")
# Territories and military addresses have no Census region. They are given
# their own bucket rather than being folded into one they are not part of.
_add("Territories", "Territories", "PR VI GU AS MP AA AE AP")

REGIONS = ["Northeast", "Midwest", "South", "West", "Territories"]
DIVISION_NAMES = [
    "New England", "Mid-Atlantic", "East North Central", "West North Central",
    "South Atlantic", "East South Central", "West South Central", "Mountain",
    "Pacific", "Territories",
]


def region_of(state: str | None) -> str | None:
    entry = DIVISIONS.get((state or "").strip().upper())
    return entry[0] if entry else None


def division_of(state: str | None) -> str | None:
    entry = DIVISIONS.get((state or "").strip().upper())
    return entry[1] if entry else None


def states_in_region(name: str) -> list[str]:
    return sorted(s for s, (r, d) in DIVISIONS.items()
                  if name in (r, d))


