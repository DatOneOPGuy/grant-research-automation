"""The benchmark list: major internationally-operating ministries.

The point of this file is prospecting by peer. A foundation that funded
Wycliffe, Samaritan's Purse and Compassion is a live prospect for any client
doing overseas work, and it is a far better signal than anything the 990-PF
says about geography -- the "International" filter keys off a foreign mailing
address, and essentially none of these organisations have one. Wycliffe is in
Orlando, Samaritan's Purse in Boone, Compassion in Colorado Springs. Around
90% of their funders are invisible to that filter.

CURATED ON PURPOSE. An inferred signal was tried first and is not good
enough: filtering grantee names for "international", "mission", "world" and
so on pulls in World Wildlife Fund, the National WWII Museum, the
International Crane Foundation and every domestic rescue mission in the
country. NTEE codes do not rescue it either, because the large evangelical
internationals are classified under Religion rather than Q (International,
Foreign Affairs) and in our data mostly carry no NTEE at all.

MATCHING. Each organisation needs both EINs and name patterns, because
neither alone works:

  - EIN alone misses most of the money. Samaritan's Purse's largest row --
    1,230 funders, $48.3M -- carries no EIN whatsoever, and every Billy
    Graham row is EIN-less. 990-PF grant schedules simply often omit it.
  - Patterns alone pull in the wrong organisations, hence `exclude`. "TEAM"
    catches Team Rubicon, "FRONTIERS" catches Medecins Sans Frontieres,
    "OPEN DOORS" catches a domestic youth programme in Ohio.

So patterns cast the net and `exclude` pulls back the false positives. Run
    python3 -m src.build_benchmark_index --review
to dump every name each entry matched; that CSV is the thing to check when
adding an organisation, because a bad pattern here silently mislabels
foundations as international prospects.

ADDING ONE. Give it a slug, a display name, a category, and patterns. Keep
patterns tight enough that the review file stays clean. `eins` is optional
and additive -- it catches rows whose name is written in a way no pattern
would survive.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BenchmarkOrg:
    slug: str
    name: str
    category: str
    patterns: tuple[str, ...]
    eins: tuple[str, ...] = ()
    exclude: tuple[str, ...] = field(default_factory=tuple)


# Categories are for grouping in the UI, so a fundraiser can pick the peers
# that look like their own client rather than the whole list.
CATEGORIES = {
    "evangelism": "Evangelism & discipleship",
    "translation": "Bible translation & distribution",
    "relief": "Relief & development",
    "child": "Child sponsorship & family",
    "medical": "Medical & water",
    "persecuted": "Persecuted church",
    "sending": "Mission sending agencies",
}

ORGS: tuple[BenchmarkOrg, ...] = (
    # --- evangelism & discipleship ------------------------------------------
    BenchmarkOrg(
        "billy-graham", "Billy Graham Evangelistic Association", "evangelism",
        patterns=("billy graham",),
        # The Wheaton College archive centre is a college department, not the
        # BGEA, and its single funder is not a BGEA donor.
        exclude=("wheaton college", "billy graham center")),
    BenchmarkOrg(
        "cru", "Cru / Campus Crusade for Christ", "evangelism",
        eins=("952814920",),
        patterns=("campus crusade", r"^cru\b", "jesus film")),
    BenchmarkOrg(
        "navigators", "The Navigators", "evangelism",
        patterns=("navigators",)),
    BenchmarkOrg(
        "luis-palau", "Luis Palau Association", "evangelism",
        patterns=("luis palau",)),
    BenchmarkOrg(
        "youth-with-a-mission", "Youth With A Mission (YWAM)", "sending",
        patterns=("youth with a mission", "ywam")),
    BenchmarkOrg(
        "trans-world-radio", "Trans World Radio", "evangelism",
        # "twr" unanchored matched Hostwriter and Cartwright Elementary.
        patterns=("trans ?world radio", r"\btwr\b")),

    # --- Bible translation & distribution -----------------------------------
    BenchmarkOrg(
        "wycliffe", "Wycliffe Bible Translators", "translation",
        eins=("951831097", "952584324"),
        patterns=("wycliffe",),
        # An Oxford theological hall, unrelated to Bible translation. The
        # Seed Company is a Wycliffe affiliate with its own entry below --
        # counting it here too would credit one grant to two ministries and
        # inflate the foundation's commitment tier.
        exclude=("wycliffe hall", "seed company")),
    BenchmarkOrg(
        "seed-company", "The Seed Company", "translation",
        # Anchored: unanchored caught QualiBasic and Germania, actual seed
        # merchants.
        patterns=(r"^(the )?seed company\b", "wycliffe seed company",
                  "^seed company the")),
    BenchmarkOrg(
        "biblica", "Biblica", "translation",
        # \b matters: "biblica" alone matched every "biblical seminary" and
        # "college of biblical studies" in the data.
        patterns=(r"\bbiblica\b",)),
    BenchmarkOrg(
        "bible-league", "Bible League International", "translation",
        patterns=(r"\bbible league\b",)),
    BenchmarkOrg(
        "gideons", "The Gideons International", "translation",
        patterns=("gideons international", r"^(the )?gideons\b"),
        # Unrelated organisations that begin with the word.
        exclude=("gideons army", "gideons promise")),
    BenchmarkOrg(
        "united-bible-societies", "United Bible Societies / American Bible",
        "translation",
        patterns=("american bible society", "united bible societ")),

    # --- relief & development -----------------------------------------------
    BenchmarkOrg(
        "samaritans-purse", "Samaritan's Purse", "relief",
        eins=("581437002",),
        patterns=("samaritan.?s? purse", "samaritan purse")),
    BenchmarkOrg(
        "world-vision", "World Vision", "child",
        eins=("951922279",),
        patterns=("world vision",),
        # A small unrelated organisation that shares the words.
        exclude=("small world vision",)),
    BenchmarkOrg(
        "food-for-the-hungry", "Food for the Hungry", "relief",
        patterns=("food for the hungry",)),
    BenchmarkOrg(
        "world-relief", "World Relief", "relief",
        patterns=(r"^world relief\b", "world relief corp"),
        # Separate denominational relief arms that share the words. Each is
        # its own organisation with its own donors.
        exclude=("lutheran world relief", "covenant world relief")),
    BenchmarkOrg(
        "lutheran-world-relief", "Lutheran World Relief", "relief",
        patterns=("lutheran world relief",)),
    BenchmarkOrg(
        "catholic-relief", "Catholic Relief Services", "relief",
        patterns=("catholic relief services",)),
    BenchmarkOrg(
        "cross-catholic", "Cross Catholic Outreach", "relief",
        # "cross catholic" alone matched every Holy Cross parish and school.
        patterns=("cross catholic outreach",)),
    BenchmarkOrg(
        "world-concern", "World Concern", "relief",
        patterns=("world concern",)),
    BenchmarkOrg(
        "world-gospel-mission", "World Gospel Mission", "sending",
        patterns=("world gospel mission",)),
    BenchmarkOrg(
        "opportunity-international", "Opportunity International", "relief",
        patterns=("opportunity international",)),
    BenchmarkOrg(
        "hope-international", "HOPE International", "relief",
        eins=("232836648",),
        # Anchored. A great many unrelated charities end in "Hope
        # International" -- Missions of Hope, Creating Hope, Prisoners of
        # Hope, Living Hope.
        patterns=(r"^hope international\b",),
        exclude=("world hope", "shared hope", "alliance for hope",
                 "boys hope", "hope international development",
                 "hope international missions", "hope international ministr",
                 "hope international school", "hope international university",
                 "hope international food")),

    # --- child sponsorship & family -----------------------------------------
    BenchmarkOrg(
        "compassion", "Compassion International", "child",
        eins=("362423707",),
        patterns=("compassion international",),
        # An assisted-dying advocacy group, nothing to do with Compassion.
        exclude=("compassion and choices",)),
    BenchmarkOrg(
        "unbound", "Unbound (Christian Foundation for Children)", "child",
        # Anchored and bounded: "unbound" matched Unbounded Learning, College
        # Unbound and Talent Unbound, none of them related.
        patterns=(r"^unbound$", "christian foundation for children"),
        exclude=("unbound now",)),
    BenchmarkOrg(
        "childfund", "ChildFund International", "child",
        patterns=("child fund international", "childfund")),

    # --- medical & water ------------------------------------------------------
    BenchmarkOrg(
        "mercy-ships", "Mercy Ships", "medical",
        patterns=("mercy ships",)),
    BenchmarkOrg(
        "living-water", "Living Water International", "medical",
        patterns=("living water international",)),
    BenchmarkOrg(
        "water-mission", "Water Mission", "medical",
        patterns=("water missions? international", "^water mission")),
    BenchmarkOrg(
        "medical-teams", "Medical Teams International", "medical",
        patterns=("medical teams international",)),
    BenchmarkOrg(
        "mission-aviation", "Mission Aviation Fellowship", "medical",
        patterns=("mission aviation fellowship",)),
    BenchmarkOrg(
        "ijm", "International Justice Mission", "relief",
        patterns=("international justice mission",)),

    # --- persecuted church ----------------------------------------------------
    BenchmarkOrg(
        "open-doors", "Open Doors", "persecuted",
        # The regional entities (Sub Saharan Africa, Middle East, Latin
        # America, Southeast Asia) are Open Doors and carry most of the money.
        patterns=("open doors",),
        # Domestic programmes that share the name.
        exclude=("open doors academy", "open doors kalamazoo")),
    BenchmarkOrg(
        "voice-of-the-martyrs", "The Voice of the Martyrs", "persecuted",
        patterns=("voice of the martyrs",)),

    # --- sending agencies -----------------------------------------------------
    BenchmarkOrg(
        "operation-mobilization", "Operation Mobilization", "sending",
        patterns=("operation mobilization",)),
    BenchmarkOrg(
        "sim", "SIM USA", "sending",
        patterns=("sim usa",)),
    BenchmarkOrg(
        "pioneers", "Pioneers", "sending",
        patterns=("^pioneers", "pioneers-?usa"),
        # A domestic youth character-education charity.
        exclude=("youth frontiers", "pioneer valley", "pioneer memorial")),
    BenchmarkOrg(
        "christar", "Christar", "sending",
        patterns=("christar",)),
    BenchmarkOrg(
        "africa-inland", "Africa Inland Mission", "sending",
        patterns=("africa inland",)),
    BenchmarkOrg(
        "team-sending", "TEAM (The Evangelical Alliance Mission)", "sending",
        patterns=("evangelical alliance mission",)),
    BenchmarkOrg(
        "partners-international", "Partners International", "sending",
        # Anchored: Community, Malaria, Asian and Social Venture Partners
        # International are four different organisations.
        patterns=(r"^(the )?partners international\b",)),
)

BY_SLUG = {o.slug: o for o in ORGS}


def validate() -> None:
    """Fail loudly on a malformed list rather than silently mismatching."""
    seen: set[str] = set()
    for org in ORGS:
        if org.slug in seen:
            raise ValueError(f"duplicate slug: {org.slug}")
        seen.add(org.slug)
        if org.category not in CATEGORIES:
            raise ValueError(f"{org.slug}: unknown category {org.category}")
        if not org.patterns and not org.eins:
            raise ValueError(f"{org.slug}: no way to match anything")
