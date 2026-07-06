"""Shared query-building helpers: filter parsing and pagination."""

SORTABLE = {
    'foundation_name', 'state', 'distributions', 'assets', 'revenue',
    'faith_alignment_score', 'faith_score_composite', 'christian_dollars_3yr',
    'application_status', 'latest_tax_year', 'christian_giving_pct',
    'total_giving',
}

SIZE_BUCKETS = {
    'lt100k': 'distributions < 100000',
    '100k-1m': 'distributions >= 100000 AND distributions < 1000000',
    '1m-10m': 'distributions >= 1000000 AND distributions < 10000000',
    'gte10m': 'distributions >= 10000000',
}

# Preset views: (filter patch dict, sort, direction). Applied server-side.
PRESETS = {
    'best-prospects': {
        'where': ["application_status = 'Accepting Applications'",
                  'faith_score_composite > 30',
                  'christian_dollars_3yr >= 100000',
                  'is_testamentary_trust = 0'],
        'sort': 'christian_dollars_3yr', 'direction': 'desc',
    },
    'top-christian-dollars': {
        'where': ['christian_dollars_3yr > 0', 'is_testamentary_trust = 0'],
        'sort': 'christian_dollars_3yr', 'direction': 'desc',
    },
    'highest-alignment': {
        'where': ['faith_score_composite > 90'],
        'sort': 'faith_score_composite', 'direction': 'desc',
    },
    'accepting': {
        'where': ["application_status = 'Accepting Applications'",
                  'is_testamentary_trust = 0'],
        'sort': 'faith_score_composite', 'direction': 'desc',
    },
}


def foundation_filters(p) -> tuple[str, list]:
    """Build WHERE clause from FoundationFilters params."""
    where, args = ['1=1'], []

    preset = PRESETS.get(p.preset or '')
    if preset:
        where.extend(preset['where'])

    if p.q:
        where.append('(foundation_name LIKE ? OR ein LIKE ? OR city LIKE ?)')
        args += [f'%{p.q}%', f'%{p.q}%', f'%{p.q}%']
    if p.states:
        marks = ','.join('?' * len(p.states))
        where.append(f'state IN ({marks})')
        args += p.states
    if p.score_min is not None:
        where.append('faith_score_composite >= ?')
        args.append(p.score_min)
    if p.score_max is not None:
        where.append('faith_score_composite <= ?')
        args.append(p.score_max)
    if p.pct_min is not None:
        where.append('christian_giving_pct >= ?')
        args.append(p.pct_min)
    if p.christian_min is not None:
        where.append('christian_dollars_3yr >= ?')
        args.append(p.christian_min)
    if p.status:
        clauses = []
        for s in p.status:
            if s == 'Unknown':
                clauses.append(
                    "(application_status IS NULL OR application_status = '')")
            else:
                clauses.append('application_status = ?')
                args.append(s)
        where.append('(' + ' OR '.join(clauses) + ')')
    if p.sizes:
        clauses = [SIZE_BUCKETS[s] for s in p.sizes if s in SIZE_BUCKETS]
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
    if p.has_filings:
        where.append("data_found = 'Yes'")
    if p.has_contact:
        where.append("(contact_person != '' AND contact_person IS NOT NULL)")
    if p.has_website:
        where.append("(website != '' AND website IS NOT NULL)")
    if p.has_phone:
        where.append("(phone != '' AND phone IS NOT NULL)")
    if p.has_deadline:
        where.append("(deadlines != '' AND deadlines IS NOT NULL)")
    # Exclude trusts/micro-funds by default unless explicitly included or a
    # preset already set its own trust rule.
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
    col = sort if sort in SORTABLE else 'faith_score_composite'
    dirn = 'ASC' if (direction or '').lower() == 'asc' else 'DESC'
    return f'ORDER BY "{col}" {dirn} NULLS LAST'
