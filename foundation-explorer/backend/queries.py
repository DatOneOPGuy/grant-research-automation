"""Shared query-building helpers: filter parsing and pagination."""

SORTABLE = {
    'foundation_name', 'state', 'distributions', 'assets', 'revenue',
    'faith_alignment_score', 'application_status', 'latest_tax_year',
    'christian_giving_pct', 'total_giving',
}

SIZE_BUCKETS = {
    'lt100k': ('distributions < 100000',),
    '100k-1m': ('distributions >= 100000 AND distributions < 1000000',),
    '1m-10m': ('distributions >= 1000000 AND distributions < 10000000',),
    'gte10m': ('distributions >= 10000000',),
}


def foundation_filters(p) -> tuple[str, list]:
    """Build WHERE clause from FoundationFilters params."""
    where, args = ['1=1'], []

    if p.q:
        where.append('(foundation_name LIKE ? OR ein LIKE ?)')
        args += [f'%{p.q}%', f'%{p.q}%']
    if p.states:
        marks = ','.join('?' * len(p.states))
        where.append(f'state IN ({marks})')
        args += p.states
    if p.score_min is not None:
        where.append('faith_alignment_score >= ?')
        args.append(p.score_min)
    if p.score_max is not None:
        where.append('faith_alignment_score <= ?')
        args.append(p.score_max)
    if p.tiers:
        clauses = []
        for t in p.tiers:
            if t == 'Unclassified':
                clauses.append('faith_tier IS NULL')
            else:
                clauses.append('faith_tier = ?')
                args.append(t)
        where.append('(' + ' OR '.join(clauses) + ')')
    if p.status:
        clauses = []
        for s in p.status:
            if s == 'Unknown':
                clauses.append(
                    "(application_status IS NULL "
                    "OR application_status = '')"
                )
            else:
                clauses.append('application_status = ?')
                args.append(s)
        where.append('(' + ' OR '.join(clauses) + ')')
    if p.sizes:
        clauses = [SIZE_BUCKETS[s][0] for s in p.sizes if s in SIZE_BUCKETS]
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
    if p.gives_state:
        where.append("states_given_to LIKE ?")
        args.append(f'%{p.gives_state}%')

    return ' AND '.join(where), args


def order_clause(sort: str | None, direction: str | None) -> str:
    col = sort if sort in SORTABLE else 'faith_alignment_score'
    dirn = 'ASC' if (direction or '').lower() == 'asc' else 'DESC'
    return f'ORDER BY "{col}" {dirn} NULLS LAST'
