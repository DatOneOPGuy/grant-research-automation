"""5-pass fuzzy name matching with normalization and tiebreaking."""

import re
from thefuzz import fuzz
from src.config import (
    STRIP_WORDS, ALIASES, FUZZY_THRESHOLD,
    ABBREVIATIONS, FKA_MARKERS,
)


def expand_abbreviations(name: str) -> str:
    """Expand common abbreviations (fam→family, tr→trust, etc.)."""
    words = name.split()
    expanded = []
    for w in words:
        expanded.append(ABBREVIATIONS.get(w, w))
    return ' '.join(expanded)


def strip_fka(name: str) -> str:
    """Strip 'FKA', 'formerly known as', etc. and everything after."""
    name_lower = name.lower()
    for marker in FKA_MARKERS:
        idx = name_lower.find(marker)
        if idx > 0:
            name = name[:idx]
            break
    return name.strip()


def strip_truncation(name: str) -> str:
    """Handle truncated names — remove trailing partial words."""
    # If name ends with a word < 4 chars that isn't a known word,
    # it's likely truncated — remove it
    words = name.split()
    if len(words) >= 2:
        last = words[-1]
        known_short = {
            'inc', 'llc', 'ltd', 'co', 'jr', 'sr', 'ii', 'iii',
            'iv', 'us', 'ny', 'ca', 'tx', 'fl', 'pa', 'oh', 'il',
        }
        if len(last) <= 3 and last not in known_short:
            words = words[:-1]
    return ' '.join(words)


def normalize(name: str) -> str:
    """Strip noise words, punctuation, and normalize whitespace."""
    name = name.lower().strip()
    name = strip_fka(name)
    name = re.sub(r'[^\w\s]', '', name)
    name = expand_abbreviations(name)
    words = name.split()
    words = [w for w in words if w not in STRIP_WORDS]
    return ' '.join(words)


def core_tokens(name: str, max_tokens: int = 3) -> str:
    """Extract first N significant tokens for partial matching."""
    normed = normalize(name)
    words = normed.split()
    return ' '.join(words[:max_tokens])


def apply_aliases(name: str) -> str:
    """Check if normalized name has a known alias."""
    normed = normalize(name)
    return ALIASES.get(normed, name)


def pick_best_with_geo(scored_candidates, city, state):
    """Tiebreak: among candidates above threshold, prefer geo match."""
    if not scored_candidates:
        return None, 0
    if len(scored_candidates) == 1:
        return scored_candidates[0]

    city_lower = (city or '').lower().strip()
    state_lower = (state or '').lower().strip()

    same_state = [
        (c, s) for c, s in scored_candidates
        if (c.get('state') or '').lower().strip() == state_lower
    ]
    pool = same_state if same_state else scored_candidates

    same_city = [
        (c, s) for c, s in pool
        if (c.get('city') or '').lower().strip() == city_lower
    ]
    pool = same_city if same_city else pool

    return pool[0]


def find_match(name, city, state, candidates):
    """
    Multi-pass matching. Returns (matched_candidate, score, pass_number)
    or (None, best_score, 0) if no match found.
    """
    normed = normalize(apply_aliases(name))

    # Pass 1: Exact on normalized name
    exact = [c for c in candidates if c['normed'] == normed]
    if len(exact) == 1:
        return exact[0], 100, 1
    if len(exact) > 1:
        best, score = pick_best_with_geo(
            [(c, 100) for c in exact], city, state
        )
        if best:
            return best, score, 1

    # Pass 2: Exact + geo
    city_lower = (city or '').lower().strip()
    state_lower = (state or '').lower().strip()
    exact_geo = [
        c for c in candidates
        if c['normed'] == normed
        and (c.get('state') or '').lower().strip() == state_lower
        and (c.get('city') or '').lower().strip() == city_lower
    ]
    if exact_geo:
        return exact_geo[0], 100, 2

    # Pass 3: Fuzzy ratio
    fuzzy = []
    for c in candidates:
        score = fuzz.ratio(normed, c['normed'])
        if score >= FUZZY_THRESHOLD:
            fuzzy.append((c, score))
    if fuzzy:
        fuzzy.sort(key=lambda x: x[1], reverse=True)
        best, score = pick_best_with_geo(fuzzy, city, state)
        if best:
            return best, score, 3

    # Pass 4: Token sort ratio
    token = []
    for c in candidates:
        score = fuzz.token_sort_ratio(normed, c['normed'])
        if score >= FUZZY_THRESHOLD:
            token.append((c, score))
    if token:
        token.sort(key=lambda x: x[1], reverse=True)
        best, score = pick_best_with_geo(token, city, state)
        if best:
            return best, score, 4

    # Pass 5: Token set ratio (handles extra/missing words)
    token_set = []
    for c in candidates:
        score = fuzz.token_set_ratio(normed, c['normed'])
        if score >= 95:  # Higher threshold for token_set (looser match)
            token_set.append((c, score))
    if token_set:
        token_set.sort(key=lambda x: x[1], reverse=True)
        best, score = pick_best_with_geo(token_set, city, state)
        if best:
            return best, score, 5

    # Pass 6: Core token match (first 2-3 significant words)
    core = core_tokens(name, max_tokens=2)
    if core and len(core) >= 4:
        core_matches = []
        for c in candidates:
            c_core = ' '.join(c['normed'].split()[:2])
            if core == c_core:
                score = fuzz.token_set_ratio(normed, c['normed'])
                core_matches.append((c, score))
        if core_matches:
            core_matches.sort(key=lambda x: x[1], reverse=True)
            best, score = pick_best_with_geo(
                core_matches, city, state
            )
            if best and score >= 80:
                return best, score, 6

    # No match — return best candidate for logging
    best_candidate = None
    best_score = 0
    for c in candidates:
        score = fuzz.ratio(normed, c['normed'])
        if score > best_score:
            best_score = score
            best_candidate = c
    return best_candidate, best_score, 0


def match_grantee_to_targets(grantee_name, target_lookup):
    """
    Check if a grantee name matches any target organization.
    Returns canonical name or None.
    """
    normed = normalize(grantee_name)

    alias_result = ALIASES.get(normed)
    if alias_result:
        return alias_result

    if normed in target_lookup:
        return target_lookup[normed]

    best_match_name = None
    best_score = 0
    for target_normed, canonical in target_lookup.items():
        score = max(
            fuzz.ratio(normed, target_normed),
            fuzz.token_sort_ratio(normed, target_normed),
            fuzz.token_set_ratio(normed, target_normed),
        )
        if score > best_score:
            best_score = score
            best_match_name = canonical

    if best_score >= FUZZY_THRESHOLD:
        return best_match_name

    return None
