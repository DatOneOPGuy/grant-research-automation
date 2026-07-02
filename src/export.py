"""Export the foundation database: one row per universe EIN.

Joins the BMF universe with parsed 990-PF profile fields, faith scores,
and states-given-to. Every row gets a ProPublica link. Foundations with
no parsed filing keep identity columns and data_found = No.
"""

import logging
import sqlite3
from collections import defaultdict

import pandas as pd

from src.config import DB_PATH
from src.profile_fields import application_status

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

UNIVERSE_CSV = 'data/universe.csv'
OUTPUT_CSV = 'foundation_database.csv'

PROFILE_SQL = """
    SELECT f.ein, f.organization_name, f.city, f.state, f.tax_year,
           f.assets, f.distributions, f.revenue, f.website, f.phone,
           f.invite_only, f.has_application_info, f.contact_person,
           f.contact_address, f.contact_phone, f.contact_email,
           f.application_format, f.deadlines, f.restrictions
    FROM foundations f
    JOIN (SELECT ein, MAX(tax_year) AS yr FROM foundations GROUP BY ein) m
      ON f.ein = m.ein AND f.tax_year = m.yr
"""

FAITH_COLS = ['faith_alignment_score', 'faith_tier', 'faith_stars',
              'faith_categories', 'christian_giving_pct',
              'years_of_faith_giving', 'total_giving', 'faith_giving']


def load_profiles(conn) -> dict[str, dict]:
    cols = [d[0] for d in conn.execute(PROFILE_SQL).description]
    return {
        row[0].zfill(9): dict(zip(cols, row))
        for row in conn.execute(PROFILE_SQL)
    }


def load_states_given(conn) -> dict[str, str]:
    states = defaultdict(set)
    for ein, state in conn.execute(
        "SELECT ein, state FROM grants "
        "WHERE state != '' AND is_foreign = 0"
    ):
        states[ein.zfill(9)].add(state)
    return {ein: '; '.join(sorted(s)) for ein, s in states.items()}


def load_faith_scores(conn) -> dict[str, dict]:
    sql = f"SELECT ein, {', '.join(FAITH_COLS)} FROM faith_scores"
    return {
        row[0].zfill(9): dict(zip(FAITH_COLS, row[1:]))
        for row in conn.execute(sql)
    }


def build_row(u, profile, states, faith) -> dict:
    ein = u['EIN']
    row = {
        'ein': ein,
        'foundation_name': profile.get('organization_name') or u['NAME'],
        'city': profile.get('city') or u['CITY'],
        'state': profile.get('state') or u['STATE'],
        'ntee_code': u.get('NTEE_CD') or '',
        'data_found': 'Yes' if profile else 'No',
        'latest_tax_year': profile.get('tax_year', ''),
        'revenue': profile.get('revenue', ''),
        'assets': profile.get('assets', ''),
        'distributions': profile.get('distributions', ''),
        'application_status': application_status(
            profile.get('invite_only') or 0,
            profile.get('has_application_info') or 0,
        ),
        'website': profile.get('website', ''),
        'phone': (profile.get('contact_phone')
                  or profile.get('phone') or ''),
        'contact_person': profile.get('contact_person', ''),
        'contact_address': profile.get('contact_address', ''),
        'contact_email': profile.get('contact_email', ''),
        'application_format': profile.get('application_format', ''),
        'deadlines': profile.get('deadlines', ''),
        'restrictions': profile.get('restrictions', ''),
        'states_given_to': states.get(ein, ''),
        'propublica_url':
            f"https://projects.propublica.org/nonprofits/organizations/"
            f"{ein}",
    }
    for col in FAITH_COLS:
        row[col] = faith.get(col, '')
    return row


def run():
    universe = pd.read_csv(UNIVERSE_CSV, dtype=str).fillna('')
    conn = sqlite3.connect(DB_PATH)
    profiles = load_profiles(conn)
    states = load_states_given(conn)
    faith = load_faith_scores(conn)
    conn.close()
    log.info("Universe %d EINs; profiles for %d, faith scores for %d",
             len(universe), len(profiles), len(faith))

    rows = [
        build_row(u, profiles.get(u['EIN'], {}), states,
                  faith.get(u['EIN'], {}))
        for u in universe.to_dict('records')
    ]
    df = pd.DataFrame(rows)
    df['faith_alignment_score'] = pd.to_numeric(
        df['faith_alignment_score'], errors='coerce'
    )
    df = df.sort_values('faith_alignment_score', ascending=False,
                        na_position='last')
    df.to_csv(OUTPUT_CSV, index=False, quoting=1)
    log.info("Wrote %d rows to %s (%d with filing data, "
             "%d accepting applications, %d invite-only)",
             len(df), OUTPUT_CSV,
             (df['data_found'] == 'Yes').sum(),
             (df['application_status'] == 'Accepting Applications').sum(),
             (df['application_status'] == 'Invite Only').sum())


if __name__ == '__main__':
    run()
