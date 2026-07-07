"""Shared query-building helpers: filter parsing and pagination."""

SORTABLE = {
    'foundation_name', 'state', 'distributions', 'assets', 'revenue',
    'christian_dollars_3yr', 'application_status', 'latest_tax_year',
    'christian_pct_floor', 'christian_pct_ceiling', 'classification_coverage',
    'total_giving', 'total_giving_3yr',
}
DEFAULT_SORT = 'christian_dollars_3yr'

SIZE_BUCKETS = {
    'lt100k': 'distributions < 100000',
    '100k-1m': 'distributions >= 100000 AND distributions < 1000000',
    '1m-10m': 'distributions >= 1000000 AND distributions < 10000000',
    'gte10m': 'distributions >= 10000000',
}

# Preset views: (filter patch dict, sort, direction). Applied server-side.
STRONG = "verdict = 'Funds Christian organizations'"
REACHABLE = ("application_status IN ('Accepting Applications', "
             "'Contact First')")

PRESETS = {
    'best-prospects': {
        'where': [STRONG, REACHABLE, 'is_testamentary_trust = 0'],
        'sort': 'christian_dollars_3yr', 'direction': 'desc',
    },
    'top-christian-dollars': {
        'where': ["verdict != 'No confirmed Christian giving'",
                  'is_testamentary_trust = 0'],
        'sort': 'christian_dollars_3yr', 'direction': 'desc',
    },
    'accepting': {
        'where': [STRONG, "application_status = 'Accepting Applications'",
                  'is_testamentary_trust = 0'],
        'sort': 'christian_dollars_3yr', 'direction': 'desc',
    },
}


LATEST_FILING_YEAR = 2024  # newest tax year with broad e-file coverage


def foundation_filters(p) -> tuple[str, list]:
    """Build WHERE clause from FoundationFilters params.

    Customer model: foundations that fund Christian organizations and can be
    approached. The default view is strong-verdict + reachable; explicit
    filters widen it.
    """
    where, args = ['1=1'], []
    preset = PRESETS.get(p.preset or '')
    if preset:
        where.extend(preset['where'])

    # --- Christian-giving verdict (customers only see Christian funders) ---
    if not preset:
        verdict = (p.verdict or 'strong').lower()
        if verdict == 'some':
            where.append("verdict = 'Some Christian giving'")
        elif verdict == 'any':
            where.append("verdict != 'No confirmed Christian giving'")
        else:  # 'strong' (default)
            where.append(STRONG)

    # --- reachability: exclude invite-only unless toggled on ---
    if not preset and not p.include_invite:
        where.append(REACHABLE)

    if p.christian_min is not None:
        where.append('christian_dollars_3yr >= ?')
        args.append(p.christian_min)
    if p.recently_active:
        where.append('most_recent_christian_year >= ?')
        args.append(LATEST_FILING_YEAR)

    if p.q:
        where.append('(foundation_name LIKE ? OR ein LIKE ? OR city LIKE ?)')
        args += [f'%{p.q}%', f'%{p.q}%', f'%{p.q}%']
    if p.states:
        marks = ','.join('?' * len(p.states))
        where.append(f'state IN ({marks})')
        args += p.states
    if p.sizes:
        clauses = [SIZE_BUCKETS[s] for s in p.sizes if s in SIZE_BUCKETS]
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
    if p.has_contact:
        where.append("(contact_person != '' AND contact_person IS NOT NULL)")
    if p.has_website:
        where.append("(website != '' AND website IS NOT NULL)")
    if p.has_phone:
        where.append("(phone != '' AND phone IS NOT NULL)")
    # Exclude trusts/micro-funds by default unless explicitly included.
    if not p.include_trusts and not preset:
        where.append('(is_testamentary_trust = 0 OR is_testamentary_trust '
                     'IS NULL)')
    if not p.include_small and not preset:
        where.append('(is_small_fund = 0 OR is_small_fund IS NULL)')

    return ' AND '.join(where), args


def order_clause(p) -> str:
    preset = PRESETS.get(p.preset or '')
    sort = p.sort
    direction = p.direction
    if preset and not p.sort:
        sort, direction = preset['sort'], preset['direction']
    col = sort if sort in SORTABLE else DEFAULT_SORT
    dirn = 'ASC' if (direction or '').lower() == 'asc' else 'DESC'
    return f'ORDER BY "{col}" {dirn} NULLS LAST'
