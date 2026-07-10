"""Faith-Based Giving Detector configuration: tags, rules, seeds, weights."""

# --- Classification thresholds ---
# LLM-classify a recipient only if it received at least one grant this size.
# Measured on 963k parsed grants: rows under $5k carry only 0.6% of dollars.
CLASSIFY_MIN_GRANT = 5_000
# Tags below this confidence are stored but do not count toward scoring.
CONFIDENCE_MIN = 70

# --- Tag vocabulary (fixed; classifier must choose from these) ---
FAITH_TAGS = [
    "Christian Ministry", "Church", "Bible Translation", "Evangelism",
    "Church Planting", "Pregnancy Center", "Christian School",
    "International Missions", "Faith-Based Education",
    "Rescue Mission", "Youth Ministry", "Medical Missions",
]
SECULAR_TAGS = [
    "Disaster Relief", "Human Trafficking", "Homelessness",
    "Food Security", "Agriculture", "Medical", "Education",
    "Arts", "Human Services", "Community Development",
    "Child Sponsorship", "Poverty", "Israel", "Humanitarian Aid",
    "Prison Ministry",
]
ALL_TAGS = FAITH_TAGS + SECULAR_TAGS

# --- Faith Alignment Score components (client-specified weights) ---
# Each component is a set of tags; component value = share of total giving
# dollars that went to recipients carrying at least one of those tags.
FAITH_COMPONENTS = {
    'explicitly_christian': {
        'weight': 40,
        'tags': set(FAITH_TAGS),
    },
    'churches': {
        'weight': 15,
        'tags': {"Church", "Church Planting"},
    },
    'missions': {
        'weight': 15,
        'tags': {"International Missions", "Medical Missions",
                 "Bible Translation"},
    },
    'evangelism': {
        'weight': 10,
        'tags': {"Evangelism", "Church Planting"},
    },
    'education': {
        'weight': 10,
        'tags': {"Christian School", "Faith-Based Education"},
    },
}
# Consistency (faith giving in every available tax year) is the 6th
# component; year scope is 2023-2025 so "every year" means max 3 years.
CONSISTENCY_WEIGHT = 10

FAITH_TIERS = [
    (95, "Dedicated Christian Funder"),
    (80, "Strong Faith-Based Funder"),
    (60, "Regular Faith-Based Giving"),
    (40, "Occasional Faith-Based Giving"),
    (0, "No Significant Faith-Based Pattern"),
]

STAR_TIERS = [
    (80, "★★★★★"),
    (60, "★★★★"),
    (40, "★★★"),
    (15, "★★"),
    (0, "★"),
]

# --- Rule-based tagging ---
# (regex on normalized-lowercase recipient name, tags). Free, so applied to
# every grant regardless of the $5k LLM threshold. Patterns are chosen for
# precision over recall — ambiguous words (hope, grace alone, temple) are
# deliberately absent; the LLM pass handles those.
RULE_PATTERNS = [
    (r'\bchurch(es)?\b', ["Church"]),
    (r'\b(parish|cathedral|chapel|archdiocese|diocese)\b', ["Church"]),
    (r'\bministr(y|ies)\b', ["Christian Ministry"]),
    (r'\b(baptist|lutheran|methodist|presbyterian|pentecostal|wesleyan|'
     r'nazarene|mennonite|episcopal|anglican|catholic)\b',
     ["Christian Ministry"]),
    (r'\bbible translat', ["Bible Translation"]),
    (r'\bbible\b', ["Christian Ministry"]),
    (r'\b(seminary|theological)\b', ["Faith-Based Education"]),
    (r'\bchristian (school|academy|college|university|education)\b',
     ["Christian School"]),
    (r'\brescue mission\b', ["Rescue Mission"]),
    (r'\bmissionar(y|ies)\b', ["International Missions"]),
    (r'\bgospel\b', ["Evangelism"]),
    (r'\bevangeli', ["Evangelism"]),
    (r'\bchurch plant', ["Church Planting"]),
    (r'\bpregnancy (care |resource )?(center|clinic)\b',
     ["Pregnancy Center"]),
    (r'\b(youth for christ|young life|awana|campus crusade)\b',
     ["Youth Ministry"]),
    (r'\b(synagogue|chabad|yeshiva|torah|hillel)\b', ["Jewish Ministry"]),
    (r'\bsalvation army\b',
     ["Christian Ministry", "Homelessness", "Disaster Relief"]),
    (r'\bchristian\b', ["Christian Ministry"]),
]

# --- Seed knowledge base ---
# Canonical recipient name -> tags (confidence 100, source 'seed').
# From the client spec table plus known target organizations.
SEED_RECIPIENTS = {
    "Samaritan's Purse": ["Christian Ministry", "Disaster Relief",
                          "International Missions"],
    "Billy Graham Evangelistic Association": ["Evangelism",
                                              "Christian Ministry"],
    "Wycliffe Bible Translators": ["Bible Translation",
                                   "International Missions"],
    "SIL International": ["Bible Translation", "International Missions"],
    "Fellowship of Christian Athletes": ["Youth Ministry", "Evangelism"],
    "Compassion International": ["Child Sponsorship", "Christian Ministry",
                                 "Poverty"],
    "World Vision": ["Christian Ministry", "Disaster Relief",
                     "International Missions"],
    "Catholic Charities": ["Christian Ministry", "Human Services"],
    "Young Life": ["Youth Ministry"],
    "Prison Fellowship": ["Evangelism", "Prison Ministry"],
    "Salvation Army": ["Christian Ministry", "Homelessness",
                       "Disaster Relief"],
    "CRU": ["Evangelism", "Youth Ministry"],
    "OM": ["International Missions"],
    "Send Relief": ["Disaster Relief", "International Missions"],
    "YWAM": ["International Missions", "Evangelism"],
    "Youth with a Mission": ["International Missions", "Evangelism"],
    "World Gospel Mission": ["International Missions"],
    "Joshua Fund": ["Israel", "Christian Ministry", "Humanitarian Aid"],
    "Medical Ambassadors International": ["Medical Missions",
                                          "Community Development",
                                          "Christian Ministry"],
    "Equipping Farmers International": ["Agriculture", "Christian Ministry",
                                        "International Missions"],
    "Christian Aid Mission": ["International Missions", "Church Planting"],
    "WorldVentures": ["International Missions", "Church Planting"],
    "Hope International": ["Christian Ministry", "Poverty"],
    "International Justice Mission": ["Christian Ministry",
                                      "Human Trafficking"],
    "Doctors without Borders": ["Medical", "Humanitarian Aid"],
    "Plant with Purpose": ["Christian Ministry", "Agriculture"],
    "World Relief": ["Christian Ministry", "Disaster Relief"],
    "SIM International": ["International Missions"],
    "Frontiers": ["International Missions"],
    "Lifewater International": ["Christian Ministry",
                                "Community Development"],
    "Voice of the Martyrs": ["Christian Ministry", "International Missions"],
    "International Fellowship of Christian and Jews": ["Jewish Ministry",
                                                       "Israel"],
    "Operation Blessing International": ["Christian Ministry",
                                         "Disaster Relief"],
    "Church World Service": ["Christian Ministry", "Disaster Relief"],
    "Hope Walks": ["Medical Missions", "Christian Ministry"],
    "Feed the Children": ["Food Security", "Poverty"],
    "Tearfund": ["Christian Ministry", "Disaster Relief"],
    "MAP International": ["Medical Missions", "Christian Ministry"],
    "Convoy of Hope": ["Christian Ministry", "Disaster Relief",
                       "Food Security"],
    "Living Water International": ["Christian Ministry",
                                   "Community Development"],
    "Heifer International": ["Agriculture", "Poverty"],
    "CURE": ["Medical Missions", "Christian Ministry"],
    "Trans World Radio": ["Evangelism", "International Missions"],
    "Global Disciples": ["Evangelism", "Church Planting"],
    "Christ for All Nations": ["Evangelism"],
    "Pioneers": ["International Missions", "Church Planting"],
    "Jesus Film Project": ["Evangelism", "International Missions"],
    "Biblica": ["Bible Translation", "Christian Ministry"],
    "GO Movement": ["Evangelism"],
    "Faith Comes by Hearing": ["Bible Translation", "Evangelism"],
    "Luis Palau Association": ["Evangelism"],
    "Alpha International": ["Evangelism", "Christian Ministry"],
    "Joshua Project": ["International Missions"],
    "Ethnos360": ["International Missions", "Church Planting",
                  "Bible Translation"],
    "Every Home for Christ": ["Evangelism"],
    "Open Doors": ["Christian Ministry", "International Missions"],
    "Christian Solidarity International": ["Christian Ministry",
                                           "Human Trafficking"],
    "Release International": ["Christian Ministry",
                              "International Missions"],
    "Navigators": ["Evangelism", "Christian Ministry"],
    "InterVarsity Christian Fellowship": ["Youth Ministry", "Evangelism"],
    "American Bible Society": ["Bible Translation", "Christian Ministry"],
    "Gideons International": ["Evangelism", "Christian Ministry"],
    "Awana": ["Youth Ministry", "Evangelism"],
    "Child Evangelism Fellowship": ["Youth Ministry", "Evangelism"],
    "Focus on the Family": ["Christian Ministry"],
    "OMF International": ["International Missions"],
    "Campus Crusade for Christ": ["Evangelism", "Youth Ministry"],
    "Billy Graham": ["Evangelism", "Christian Ministry"],
}
