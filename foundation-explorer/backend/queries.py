"""Shared query-building helpers: filter parsing and pagination."""

SORTABLE = {
    'foundation_name', 'state', 'distributions', 'assets', 'revenue',
    'christian_dollars_3yr', 'christian_recipient_count', 'total_giving_3yr',
    'typical_grant_size', 'largest_christian_grant', 'application_status',
    'latest_tax_year',
}
DEFAULT_SORT = 'christian_dollars_3yr'

# US Census regions -> state lists (for the region quick-select).
REGIONS = {
    'northeast': ['CT', 'ME', 'MA', 'NH', 'RI', 'VT', 'NJ', 'NY', 'PA'],
    'southeast': ['DE', 'FL', 'GA', 'MD', 'NC', 'SC', 'VA', 'DC', 'WV',
                  'AL', 'KY', 'MS', 'TN', 'AR', 'LA'],
    'midwest': ['IL', 'IN', 'MI', 'OH', 'WI', 'IA', 'KS', 'MN', 'MO',
                'NE', 'ND', 'SD'],
    'southwest': ['AZ', 'NM', 'OK', 'TX'],
    'west': ['CO', 'ID', 'MT', 'NV', 'UT', 'WY', 'AK', 'CA', 'HI', 'OR', 'WA'],
}

ASSET_BUCKETS = {
    'lt1m': 'assets < 1000000',
    '1m-10m': 'assets >= 1000000 AND assets < 10000000',
    '10m-100m': 'assets >= 10000000 AND assets < 100000000',
    'gte100m': 'assets >= 100000000',
}
TYPICAL_BUCKETS = {
    'lt10k': 'typical_grant_size < 10000',
    '10k-50k': 'typical_grant_size >= 10000 AND typical_grant_size < 50000',
    '50k-250k': 'typical_grant_size >= 50000 AND typical_grant_size < 250000',
    'gte250k': 'typical_grant_size >= 250000',
}

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

    # --- default scope: strong verdict (the verdict is no longer a filter,
    # but customers still only see confirmed Christian funders) ---
    if not preset:
        where.append(STRONG)

    # --- reachability: exclude invite-only unless toggled on ---
    if not preset and not p.include_invite:
        where.append(REACHABLE)

    # --- Christian-giving depth ---
    if p.min_orgs is not None:
        where.append('christian_recipient_count >= ?')
        args.append(p.min_orgs)
    if p.christian_min is not None:
        where.append('christian_dollars_3yr >= ?')
        args.append(p.christian_min)
    if p.recently_active:
        where.append('most_recent_christian_year >= ?')
        args.append(LATEST_FILING_YEAR)
    if p.traditions:
        marks = ','.join('?' * len(p.traditions))
        where.append(f'predominant_tradition IN ({marks})')
        args += p.traditions

    # --- grant-size behavior ---
    if p.typical_sizes:
        clauses = [TYPICAL_BUCKETS[s] for s in p.typical_sizes
                   if s in TYPICAL_BUCKETS]
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
    if p.largest_min is not None:
        where.append('largest_christian_grant >= ?')
        args.append(p.largest_min)

    # --- reachability detail ---
    if p.status:
        marks = ','.join('?' * len(p.status))
        where.append(f'application_status IN ({marks})')
        args += p.status
    if p.has_contact:
        where.append("(contact_person != '' AND contact_person IS NOT NULL)")
    if p.has_website:
        where.append("(website != '' AND website IS NOT NULL)")
    if p.has_phone:
        where.append("(phone != '' AND phone IS NOT NULL)")
    if p.has_deadline:
        where.append("(deadlines != '' AND deadlines IS NOT NULL "
                     "AND upper(deadlines) NOT IN ('NONE', 'N/A'))")

    # --- geography ---
    if p.states:
        marks = ','.join('?' * len(p.states))
        where.append(f'state IN ({marks})')
        args += p.states
    if p.region and p.region in REGIONS:
        rstates = REGIONS[p.region]
        marks = ','.join('?' * len(rstates))
        where.append(f'state IN ({marks})')
        args += rstates
    if p.gives_in_state:
        where.append('states_given_to LIKE ?')
        args.append(f'%{p.gives_in_state}%')

    # --- foundation profile ---
    if p.sizes:
        clauses = [SIZE_BUCKETS[s] for s in p.sizes if s in SIZE_BUCKETS]
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
    if p.asset_buckets:
        clauses = [ASSET_BUCKETS[s] for s in p.asset_buckets
                   if s in ASSET_BUCKETS]
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
    if p.actively_giving:
        where.append('is_actively_giving = 1')

    if p.q:
        where.append('(foundation_name LIKE ? OR ein LIKE ? OR city LIKE ?)')
        args += [f'%{p.q}%', f'%{p.q}%', f'%{p.q}%']

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
