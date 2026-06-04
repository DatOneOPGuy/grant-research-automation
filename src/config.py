"""Configuration: keywords, target orgs, aliases, and scoring weights."""

# --- Scoring Weights (must total 100) ---
SCORE_WEIGHTS = {
    'grantee': 35,
    'keyword': 30,
    'international': 25,
    'focus_area': 10,
}

# Recency multipliers by tax year
RECENCY_MULTIPLIER = {
    2024: 1.2,
    2023: 1.0,
}

# --- Grantee point schedule (diminishing returns) ---
GRANTEE_POINT_SCHEDULE = [12, 8, 6, 4]  # 5th+ = 2 pts each
GRANTEE_5TH_PLUS_PTS = 2
GRANTEE_LARGE_DONATION_THRESHOLD = 25_000
GRANTEE_LARGE_DONATION_BONUS = 2
GRANTEE_MAX_LARGE_BONUS = 5

# --- Fuzzy matching ---
FUZZY_THRESHOLD = 90

# --- Target Organizations (53) ---
TARGET_ORGANIZATIONS = [
    "Samaritan's Purse",
    "Campus Crusade for Christ",
    "World Vision",
    "Billy Graham Evangelistic Association",
    "Hope International",
    "International Justice Mission",
    "Doctors without Borders",
    "Plant with Purpose",
    "World Relief",
    "Compassion International",
    "CRU",
    "SIM International",
    "Frontiers",
    "Lifewater International",
    "Voice of the Martyrs",
    "International Fellowship of Christian and Jews",
    "Operation Blessing International",
    "Church World Service",
    "Hope Walks",
    "YWAM",
    "Youth with a Mission",
    "Young Life",
    "Feed the Children",
    "Salvation Army",
    "Tearfund",
    "MAP International",
    "Convoy of Hope",
    "Living Water International",
    "Christian Aid Mission",
    "WorldVentures",
    "Heifer International",
    "CURE",
    "Wycliffe Bible Translators",
    "SIL International",
    "Trans World Radio",
    "OM",
    "Operation Mobilization",
    "Global Disciples",
    "Christ for All Nations",
    "Pioneers",
    "Jesus Film Project",
    "Biblica",
    "GO Movement",
    "Faith Comes by Hearing",
    "Luis Palau Association",
    "Alpha International",
    "Joshua Project",
    "Ethos360",
    "Every Home for Christ",
    "Open Doors",
    "Christian Solidarity International",
    "Release International",
]

# --- Manual Alias Map ---
# Maps alternate names → canonical name from TARGET_ORGANIZATIONS
# Keys should be lowercase normalized
ALIASES = {
    "campus crusade for christ": "CRU",
    "campus crusade": "CRU",
    "cru international": "CRU",
    "world vision international": "World Vision",
    "world vision inc": "World Vision",
    "samaritans purse": "Samaritan's Purse",
    "samaritan purse": "Samaritan's Purse",
    "franklin graham": "Samaritan's Purse",
    "billy graham evangelistic assn": "Billy Graham Evangelistic Association",
    "bgea": "Billy Graham Evangelistic Association",
    "ijm": "International Justice Mission",
    "msf": "Doctors without Borders",
    "medecins sans frontieres": "Doctors without Borders",
    "doctors without borders usa": "Doctors without Borders",
    "ywam": "Youth with a Mission",
    "youth with a mission": "YWAM",
    "wycliff bible translators": "Wycliffe Bible Translators",
    "wycliffe": "Wycliffe Bible Translators",
    "operation mobilization": "OM",
    "operation mobilisation": "OM",
    "om international": "OM",
    "compassion intl": "Compassion International",
    "heifer intl": "Heifer International",
    "heifer project": "Heifer International",
    "salvation army": "Salvation Army",
    "the salvation army": "Salvation Army",
    "young life inc": "Young Life",
    "feed the children inc": "Feed the Children",
    "map intl": "MAP International",
    "sim usa": "SIM International",
    "sim": "SIM International",
    "sil": "SIL International",
    "trans world radio inc": "Trans World Radio",
    "twr": "Trans World Radio",
    "voice of the martyrs": "Voice of the Martyrs",
    "vom": "Voice of the Martyrs",
}

# --- Keywords grouped by cluster ---
KEYWORD_CLUSTERS = {
    "religious_identity": [
        "Christian", "Christianity", "Catholic", "Episcopal",
        "Methodist", "Baptist", "Presbyterian", "Christ",
        "Church", "Faith", "Faith Based", "Bible",
        "Scripture", "Gospel", "Missionary",
    ],
    "mission_outreach": [
        "Ministry", "Ministries", "Mission", "Missions",
        "Evangelism", "Disciple", "Discipleship", "Hope",
        "Relief", "Refugee", "Humanitarian", "Orphan",
        "Unreached", "Indigenous", "Cross-cultural",
    ],
    "geography": [
        "Africa", "South America", "Latin America",
        "Middle East", "Israel", "Asia", "Global",
    ],
}

# Flatten for quick lookup
ALL_KEYWORDS = []
for cluster_keywords in KEYWORD_CLUSTERS.values():
    ALL_KEYWORDS.extend(cluster_keywords)

# Compound phrases that must be matched as whole phrases
COMPOUND_KEYWORDS = [
    "Faith Based", "Latin America", "South America",
    "Middle East", "Cross-cultural",
]

# Field weights for keyword scoring
KEYWORD_FIELD_WEIGHTS = {
    'charitable_activities': 3,
    'grant_purpose': 2,
    'organization_name': 1,
}

# Cluster bonus points
CLUSTER_BONUS_TWO = 3
CLUSTER_BONUS_ALL = 5

# --- Name normalization noise words ---
STRIP_WORDS = frozenset([
    'foundation', 'inc', 'incorporated', 'corp', 'corporation',
    'trust', 'fund', 'charitable', 'philanthropy', 'philanthropic',
    'organization', 'org', 'association', 'assoc', 'llc', 'ltd',
    'the', 'a', 'an', 'of', 'for', 'and', '&', 'fdn', 'fdtn',
])

# --- Abbreviation expansions (applied before normalization) ---
ABBREVIATIONS = {
    'fam': 'family',
    'tr': 'trust',
    'char': 'charitable',
    'fdtn': 'foundation',
    'fdn': 'foundation',
    'intl': 'international',
    'natl': 'national',
    'ctr': 'center',
    'svcs': 'services',
    'mgmt': 'management',
    'dev': 'development',
    'educ': 'education',
    'comm': 'community',
    'assn': 'association',
}

# Words/phrases to strip everything after (in FKA cleanup)
FKA_MARKERS = [
    'fka', 'formerly known as', 'formerly', 'f/k/a',
    'dba', 'd/b/a', 'doing business as',
    'aka', 'a/k/a', 'also known as',
]

# --- IRS download config ---
IRS_INDEX_BASE = "https://www.irs.gov/charities-non-profits/form-990-series-downloads"
IRS_YEARS = [2023, 2024]
DATA_DIR = "data"
RAW_DIR = "data/raw"
DB_PATH = "data/grants.db"
