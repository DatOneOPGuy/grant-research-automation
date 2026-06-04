"""Parse IRS 990-PF XML files into SQLite database."""

import os
import sqlite3
import logging
from pathlib import Path

from lxml import etree

from src.config import DB_PATH, RAW_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

# IRS e-file XML namespaces (varies by version)
NAMESPACES = {
    'irs': 'http://www.irs.gov/efile',
}


def create_tables(conn: sqlite3.Connection):
    """Create SQLite tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS foundations (
            ein TEXT,
            organization_name TEXT,
            city TEXT,
            state TEXT,
            country TEXT DEFAULT 'US',
            assets INTEGER,
            distributions INTEGER,
            has_grants INTEGER,
            tax_year INTEGER,
            PRIMARY KEY (ein, tax_year)
        );

        CREATE TABLE IF NOT EXISTS grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ein TEXT,
            grantee_name TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            is_foreign INTEGER DEFAULT 0,
            amount INTEGER,
            purpose TEXT,
            tax_year INTEGER
        );

        CREATE TABLE IF NOT EXISTS charitable_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ein TEXT,
            description TEXT,
            expenses INTEGER,
            tax_year INTEGER
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ein TEXT,
            name TEXT,
            title TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_grants_ein
            ON grants(ein);
        CREATE INDEX IF NOT EXISTS idx_activities_ein
            ON charitable_activities(ein);
        CREATE INDEX IF NOT EXISTS idx_foundations_name
            ON foundations(organization_name);
    """)


def _find_text(element, xpath, ns=None):
    """Safely extract text from an XML element."""
    if ns:
        result = element.find(xpath, ns)
    else:
        result = element.find(xpath)
    return result.text.strip() if result is not None and result.text else ''


def _find_int(element, xpath, ns=None):
    """Extract integer from XML, return 0 if missing."""
    text = _find_text(element, xpath, ns)
    try:
        return int(float(text)) if text else 0
    except (ValueError, TypeError):
        return 0


def detect_namespace(root):
    """Detect the IRS namespace from the root element."""
    tag = root.tag
    if '{' in tag:
        ns = tag.split('}')[0] + '}'
        return {'irs': ns[1:-1]}
    return {}


def parse_foundation_header(root, ns):
    """Extract foundation-level info from 990-PF header."""
    # Try multiple possible paths for EIN
    ein = (
        _find_text(root, './/irs:Filer/irs:EIN', ns) or
        _find_text(root, './/irs:EIN', ns) or
        _find_text(root, './/EIN')
    )

    name = (
        _find_text(root, './/irs:Filer/irs:BusinessName/'
                   'irs:BusinessNameLine1Txt', ns) or
        _find_text(root, './/irs:Filer/irs:BusinessName/'
                   'irs:BusinessNameLine1', ns) or
        _find_text(root, './/irs:BusinessName/'
                   'irs:BusinessNameLine1Txt', ns) or
        ''
    )

    city = _find_text(
        root, './/irs:Filer/irs:USAddress/irs:CityNm', ns
    ) or _find_text(
        root, './/irs:Filer/irs:USAddress/irs:City', ns
    )

    state = _find_text(
        root, './/irs:Filer/irs:USAddress/irs:StateAbbreviationCd', ns
    ) or _find_text(
        root, './/irs:Filer/irs:USAddress/irs:State', ns
    )

    tax_year = (
        _find_text(root, './/irs:TaxYr', ns) or
        _find_text(root, './/irs:TaxYear', ns) or
        ''
    )

    assets = _find_int(
        root, './/irs:FMVAssetsEOYAmt', ns
    ) or _find_int(
        root, './/irs:TotalAssetsEOYAmt', ns
    )

    distributions = _find_int(
        root, './/irs:TotDistriAndExpensesRevAndExpnssAmt', ns
    )

    return {
        'ein': ein,
        'organization_name': name,
        'city': city,
        'state': state,
        'country': 'US',
        'assets': assets,
        'distributions': distributions,
        'tax_year': int(tax_year) if tax_year.isdigit() else 0,
    }


def parse_grants(root, ns, ein, tax_year):
    """Extract Part XV grantee list from 990-PF."""
    grants = []

    # Try multiple grant element paths
    grant_paths = [
        './/irs:GrantOrContributionPdDurYrGrp',
        './/irs:GrantOrContriPaidDuringYear',
        './/irs:GrantOrContriApprvForFutGrp',
    ]

    for path in grant_paths:
        elements = root.findall(path, ns)
        for elem in elements:
            name = (
                _find_text(elem, 'irs:RecipientBusinessName/'
                           'irs:BusinessNameLine1Txt', ns) or
                _find_text(elem, 'irs:RecipientBusinessName/'
                           'irs:BusinessNameLine1', ns) or
                _find_text(elem, 'irs:RecipientPersonNm', ns) or
                ''
            )
            city = (
                _find_text(elem, 'irs:RecipientUSAddress/'
                           'irs:CityNm', ns) or
                _find_text(elem, 'irs:RecipientUSAddress/'
                           'irs:City', ns) or
                ''
            )
            state = (
                _find_text(elem, 'irs:RecipientUSAddress/'
                           'irs:StateAbbreviationCd', ns) or
                _find_text(elem, 'irs:RecipientUSAddress/'
                           'irs:State', ns) or
                ''
            )
            country = 'US'
            is_foreign = 0

            # Check for foreign address
            foreign = elem.find(
                'irs:RecipientForeignAddress', ns
            )
            if foreign is not None:
                is_foreign = 1
                country = (
                    _find_text(foreign, 'irs:CountryCd', ns) or
                    _find_text(foreign, 'irs:Country', ns) or
                    'FOREIGN'
                )

            amount = _find_int(elem, 'irs:Amt', ns) or _find_int(
                elem, 'irs:Amount', ns
            )
            purpose = (
                _find_text(elem, 'irs:GrantOrContributionPurposeTxt',
                           ns) or
                _find_text(elem, 'irs:PurposeOfGrantOrContriTxt',
                           ns) or
                ''
            )

            if name:
                grants.append({
                    'ein': ein,
                    'grantee_name': name,
                    'city': city,
                    'state': state,
                    'country': country,
                    'is_foreign': is_foreign,
                    'amount': amount,
                    'purpose': purpose,
                    'tax_year': tax_year,
                })

    return grants


def parse_charitable_activities(root, ns, ein, tax_year):
    """Extract charitable activity descriptions."""
    activities = []

    activity_paths = [
        './/irs:DescriptionOfActivity',
        './/irs:ActivityOrProgramDescription',
        './/irs:Desc',
    ]

    for path in activity_paths:
        elements = root.findall(path, ns)
        for elem in elements:
            desc = elem.text.strip() if elem.text else ''
            if desc:
                activities.append({
                    'ein': ein,
                    'description': desc,
                    'expenses': 0,
                    'tax_year': tax_year,
                })

    # Also check program service accomplishments
    psa_paths = [
        './/irs:ProgramSrvcAccomplishmentGrp',
        './/irs:ProgramServiceAccomplishment',
    ]
    for path in psa_paths:
        elements = root.findall(path, ns)
        for elem in elements:
            desc = (
                _find_text(elem, 'irs:DescriptionProgramSrvcAccomTxt',
                           ns) or
                _find_text(elem, 'irs:ActivityOrMissionDesc', ns) or
                ''
            )
            expenses = _find_int(elem, 'irs:ExpenseAmt', ns)
            if desc:
                activities.append({
                    'ein': ein,
                    'description': desc,
                    'expenses': expenses,
                    'tax_year': tax_year,
                })

    return activities


def parse_xml_file(filepath: str):
    """Parse a single 990-PF XML file. Returns parsed data dict."""
    try:
        tree = etree.parse(filepath)
        root = tree.getroot()
    except etree.XMLSyntaxError as e:
        log.warning("XML parse error in %s: %s", filepath, e)
        return None

    ns = detect_namespace(root)
    if not ns:
        log.warning("No namespace found in %s", filepath)
        return None

    # Check if this is a 990-PF (not 990 or 990-EZ)
    root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    return_type = _find_text(root, './/irs:ReturnTypeCd', ns)

    header = parse_foundation_header(root, ns)
    if not header['ein']:
        log.debug("No EIN found in %s, skipping", filepath)
        return None

    tax_year = header['tax_year']
    ein = header['ein']

    grants = parse_grants(root, ns, ein, tax_year)
    header['has_grants'] = 1 if grants else 0

    activities = parse_charitable_activities(
        root, ns, ein, tax_year
    )

    return {
        'foundation': header,
        'grants': grants,
        'activities': activities,
    }


def insert_parsed_data(conn, data):
    """Insert parsed 990 data into SQLite."""
    fdn = data['foundation']
    conn.execute(
        """INSERT OR REPLACE INTO foundations
           (ein, organization_name, city, state, country,
            assets, distributions, has_grants, tax_year)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (fdn['ein'], fdn['organization_name'], fdn['city'],
         fdn['state'], fdn['country'], fdn['assets'],
         fdn['distributions'], fdn['has_grants'],
         fdn['tax_year']),
    )

    for g in data['grants']:
        conn.execute(
            """INSERT INTO grants
               (ein, grantee_name, city, state, country,
                is_foreign, amount, purpose, tax_year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (g['ein'], g['grantee_name'], g['city'],
             g['state'], g['country'], g['is_foreign'],
             g['amount'], g['purpose'], g['tax_year']),
        )

    for a in data['activities']:
        conn.execute(
            """INSERT INTO charitable_activities
               (ein, description, expenses, tax_year)
               VALUES (?, ?, ?, ?)""",
            (a['ein'], a['description'], a['expenses'],
             a['tax_year']),
        )


def run():
    """Parse all XML files in RAW_DIR into SQLite."""
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    xml_files = list(Path(RAW_DIR).glob('*.xml'))
    log.info("Found %d XML files to parse", len(xml_files))

    parsed = 0
    errors = 0

    for i, filepath in enumerate(xml_files):
        if i % 1000 == 0 and i > 0:
            log.info("Parsed %d / %d files...", i, len(xml_files))
            conn.commit()

        data = parse_xml_file(str(filepath))
        if data:
            insert_parsed_data(conn, data)
            parsed += 1
        else:
            errors += 1

    conn.commit()

    # Log stats
    fdn_count = conn.execute(
        "SELECT COUNT(*) FROM foundations"
    ).fetchone()[0]
    grant_count = conn.execute(
        "SELECT COUNT(*) FROM grants"
    ).fetchone()[0]

    log.info(
        "Done. Parsed %d files (%d errors). "
        "DB has %d foundations, %d grants.",
        parsed, errors, fdn_count, grant_count,
    )
    conn.close()


if __name__ == '__main__':
    run()
