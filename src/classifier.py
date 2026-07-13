"""Rule-based recipient classifier (no LLM).

Classifies a grant-recipient name into a religious tradition using ordered,
word-boundary-aware pattern matching. First match wins, in this order:
  1. Messianic (fires before Jewish exclusion)
  2. Exclusions: Jewish / LDS / Christian Science / Jehovah's Witness /
     Unitarian / Muslim / other religions  -> non-Christian
  3. Catholic / Orthodox                    -> Christian
  4. Protestant / Evangelical               -> Christian
  5. Secular override (only if no religious signal)  -> non-Christian
  6. Uncategorized (None)

Ambiguous words (grace, hope, faith, trinity, bethel, temple, providence,
sacred, shalom) do NOT classify on their own — they require a second
Christian signal. Saint names classify Catholic unless a hospital/medical/
research/university override with no other Christian signal applies.
"""

import re

# --- helpers -------------------------------------------------------------

def _rx(words):
    """Word-boundary alternation regex for a list of phrases."""
    parts = [re.escape(w.strip()) for w in words if w.strip()]
    return re.compile(r'\b(?:' + '|'.join(parts) + r')', re.IGNORECASE)


# --- 1. Messianic (before Jewish exclusion) ------------------------------
MESSIANIC = _rx([
    'jews for jesus', 'chosen people ministries', 'messianic', 'yeshua',
    'jewish voice ministries', 'ariel ministries', 'maoz israel',
])

# --- 2. Exclusions (non-Christian) ---------------------------------------
JEWISH = _rx([
    'yeshiva', 'hebrew academy', 'hebrew school', 'hebrew day', 'jewish',
    'torah', 'rabbinical', 'rabbi', 'chabad', 'lubavitch', 'hasidic',
    'chasidic', 'synagogue', 'kollel', 'hillel', 'mesorah', "b'nai",
    'bnai', 'bnos', 'temple beth', 'temple emanu', 'temple israel',
    'temple sinai', 'congregation beth', 'congregation bnai', 'beth jacob',
    'beth israel', 'beth medrash', 'bais yaakov', 'jewish federation',
    'jewish community', 'jcc', 'jewish family', 'jewish national fund',
    'anti-defamation', 'holocaust', 'shoah', 'yad vashem', 'kehillah',
    'midrasha', 'aish', 'ohr somayach', 'orthodox union', 'hadassah',
    'birthright israel', 'zionist', 'israel bonds', 'american jewish',
    'united jewish', 'jewish theological', 'hebrew union', 'yeshiva university',
])
CHRISTIAN_SCIENCE = _rx([
    'christian science', 'church of christ scientist', 'principia',
    'christian scientist', 'mary baker eddy',
])
MORMON = _rx([
    'latter-day saints', 'latter day saints', 'brigham young', 'byu ',
    'mormon', 'deseret', 'book of mormon', 'nauvoo', 'tabernacle choir',
    'familysearch', 'church of jesus christ of latter',
])
JW = _rx(['jehovah', 'watchtower', 'watch tower', 'kingdom hall'])
UNITARIAN = _rx([
    'unitarian', 'universalist', 'ethical culture', 'ethical society',
])
MUSLIM = _rx([
    'islamic', 'muslim', 'mosque', 'masjid', 'madrasa', 'madrassa',
    'quran', "qur'an", 'koran', 'zakat', 'imam', 'sufi', 'ahmadiyya',
])
OTHER_RELIGION = _rx([
    'hindu', 'vedic', 'ashram', 'hare krishna', 'iskcon', 'vedanta',
    'buddhist', 'buddha', 'dharma', 'sangha', 'zen ', 'tibetan',
    'dalai lama', 'sikh', 'gurdwara', 'khalsa', "baha'i", 'bahai', 'jain',
    'zoroastrian', 'wiccan', 'pagan', 'druid',
])

# --- 3. Catholic / Orthodox ----------------------------------------------
CATHOLIC = _rx([
    'catholic', 'diocese', 'archdiocese', 'eparchy', 'jesuit',
    'society of jesus', 'franciscan', 'capuchin', 'dominican',
    'order of preachers', 'salesian', 'don bosco', 'benedictine', 'abbey',
    'monastery', 'priory', 'carmelite', 'augustinian', 'vincentian',
    'marianist', 'marist', 'redemptorist', 'passionist', 'oratorian',
    'opus dei', 'legionaries of christ', 'jesus crucified', 'sister servants',
    'christian brothers', 'de la salle',
    'lasallian', 'sisters of', 'daughters of charity', 'missionaries of charity',
    'little sisters of the poor', 'poor clares', 'felician', 'ursuline',
    'knights of columbus', 'knights of malta', 'catholic charities',
    'catholic relief', 'cross catholic', 'catholic extension', 'catholic near east',
    'aid to the church', 'food for the poor', 'st vincent de paul',
    'society of st vincent', 'our lady', 'notre dame', 'sacred heart',
    'blessed sacrament', 'immaculate', 'annunciation', 'corpus christi',
    'guadalupe', 'of fatima', 'fatima shrine', 'lourdes', 'mount carmel',
    'perpetual adoration',
    'loyola', 'gonzaga', 'villanova', 'georgetown university',
    'georgetown prep', 'fordham', 'marquette university',
    'st bonaventure', 'st louis university', 'creighton',
    'xavier university', 'st xavier', 'duquesne',
    'seton hall', 'providence college', 'boston college', 'holy cross',
    'franciscan university', 'ave maria', 'thomas aquinas', 'christendom',
    'benedictine college', 'catholic university', 'pontifical', 'vatican',
    'holy see', 'diocesan', 'newman center', 'newman club', 'word on fire',
    'ewtn', 'eternal word', 'catholic answers', 'augustine institute',
])
ORTHODOX = _rx([
    'greek orthodox', 'russian orthodox', 'antiochian orthodox',
    'serbian orthodox', 'eastern orthodox', 'oriental orthodox', 'coptic',
    'armenian apostolic', 'ethiopian orthodox', 'syriac orthodox',
    'orthodox church', 'orthodox christian', 'st vladimir', 'st tikhon',
    'theotokos', 'orthodox christian mission', 'iocc',
    'orthodox church in america', 'malankara', 'antiochian', 'philoptochos',
    'st nektarios',
])

# --- 4. Protestant / Evangelical -----------------------------------------
PROTESTANT = _rx([
    # ministry structure / activity
    'ministries', 'ministry', 'missions', 'missionary', 'mission society',
    'gospel', 'evangel', 'evangelism', 'evangelistic', 'evangelical',
    'discipleship', 'crusade', 'revival', 'awakening', 'worship center',
    'christian center', 'christian fellowship', 'christian academy',
    'christian school', 'christian ministries', 'christian outreach',
    'christian counseling', 'christian community', 'christian life',
    'bible church', 'bible institute', 'bible college', 'bible fellowship',
    'bible study fellowship', 'bible league', 'word of god', 'word of life',
    'word of faith', 'living word', 'good news', 'glad tidings', 'born again',
    # denominations
    'baptist', 'methodist', 'wesleyan', 'presbyterian', 'lutheran',
    'pentecostal', 'assemblies of god', 'assembly of god', 'church of god',
    'church of christ', 'nazarene', 'anglican', 'episcopal', 'mennonite',
    'amish', 'brethren', 'reformed', 'evangelical free', 'foursquare',
    'covenant church', 'adventist', 'salvation army', 'quaker',
    'friends church', 'vineyard', 'calvary chapel', 'acts 29',
    'sovereign grace', 'navigators', 'willow creek', 'full gospel',
    'moravian', 'anabaptist', 'charismatic', 'nondenominational',
    'non-denominational', 'interdenominational', 'community church',
    # phrasing that is clearly Christian
    'jesus', 'christ church', 'christ fellowship', 'christ community',
    'christ the king', 'christ centered', 'christ for', 'great commission',
    'good shepherd', 'the potter', 'upper room', 'maranatha', 'hosanna',
    'agape', 'koinonia', 'resurrection', 'lamb of god', 'prince of peace',
    # parachurch / named
    'cru ', 'campus crusade', 'athletes in action', 'intervarsity',
    'inter-varsity', 'young life', 'youth for christ', 'fellowship of christian',
    'ywam', 'youth with a mission', 'wycliffe', 'sil international',
    'seed company', 'world vision', 'compassion international',
    'samaritan', 'voice of the martyrs', 'open doors', 'prison fellowship',
    'focus on the family', 'billy graham', 'franklin graham', 'luis palau',
    'harvest crusade', 'gideons', 'awana', 'child evangelism',
    'precept ministries', 'walk thru the bible', 'our daily bread',
    'in touch ministries', 'ligonier', 'desiring god', 'grace to you',
    'answers in genesis', 'ethnos360', 'new tribes', 'pioneers', 'frontiers',
    'the evangelical alliance', 'serving in mission', 'trans world radio',
    'far east broadcasting', 'jesus film', 'biblica', 'american bible society',
    'international bible society', 'lockman', 'tyndale house',
    'gospel for asia', 'east west ministries', 'e3 partners', 'i am second',
    'moody bible', 'wheaton college', 'biola', 'liberty university',
    'cedarville', 'dallas theological', 'gordon-conwell', 'trinity evangelical',
    'westminster theological', 'reformed theological', 'baptist theological',
    'denver seminary', 'bethel seminary', 'asbury', 'covenant seminary',
    'union gospel mission', 'rescue mission', 'water mission',
    'living water international', 'hope international', 'international justice mission',
    'cure international', 'mercy ships', 'convoy of hope', 'teen challenge',
    'celebrate recovery', 'victory outreach', 'bethany christian',
    'lifeline children', 'show hope', 'world orphans', 'lifesong for orphans',
    'operation blessing', 'christian broadcasting', 'the 700 club',
    'inspiration ministries', 'daystar', 'trinity broadcasting', 'salem media',
    'care net', 'heartbeat international', 'crisis pregnancy',
    'pregnancy resource', 'pregnancy center', 'kairos', 'church planting',
    'seminary', 'theological seminary', 'chaplain', 'chaplaincy',
])

# Ambiguous words: classify Christian ONLY with a second Christian signal.
AMBIGUOUS = _rx([
    'grace', 'hope', 'faith', 'trinity', 'bethel', 'bethany', 'providence',
    'sacred', 'shalom', 'redeemer', 'cornerstone', 'lighthouse', 'new life',
    'new hope', 'fellowship', 'outreach', 'crossroads', 'covenant',
    'sanctuary', 'shepherd', 'refuge', 'zion', 'harvest', 'cathedral',
    'chapel', 'parish', 'holy', 'first church', 'community church',
])
CHRISTIAN_SIGNAL = _rx([
    'christ', 'christian', 'jesus', 'gospel', 'church', 'ministr', 'bible',
    'faith', 'baptist', 'catholic', 'god', 'lord', 'savior', 'saviour',
    'kingdom', 'disciple', 'evangel', 'mission', 'chapel', 'parish',
])

# Explicit Protestant denominations. These must beat the saint/Catholic
# vocabulary: "St. Peter's Evangelical Lutheran Church" is Lutheran, and an
# "Episcopal Diocese" is Episcopal, not Catholic.
PROT_DENOMINATION = _rx([
    'baptist', 'methodist', 'presbyterian', 'lutheran', 'episcopal',
    'epsicopal',  # (sic) recurring typo in 990-PF grant schedules
    'anglican', 'wesleyan', 'pentecostal', 'nazarene', 'mennonite',
    'moravian', 'adventist', 'ame zion', 'assemblies of god',
    'assembly of god', 'evangelical',
])

# Saint prefix and the medical/secular override for it.
SAINT = re.compile(r'\b(st\.?|saint|sts\.?)\s+[a-z]', re.IGNORECASE)
# "ST"/"Saint" that is a street, state, or place name — NOT a saint prefix:
# "92ND ST Y", "KENNESAW ST UNIV", "ST LOUIS MARATHON", "ST JOSEPH COUNTY".
SAINT_PLACE = re.compile(
    r'\b(?:\d+(?:st|nd|rd|th)\s+st\b'
    r'|(?:st\.?|saint)\s+(?:louis|petersburg|croix|simons?\s+island)\b'
    r'|st\.?\s+\w+s?\s+county\b'
    r'|st\s+univ(?:ersity)?\b)', re.IGNORECASE)
# Secular-sounding "Big Brothers Big Sisters" must never match 'sisters of'.
BBBS = re.compile(r'\bbig\s+brothers[\s-]+big\s+sisters\b', re.IGNORECASE)
# An explicit religious word blocks the secular institution-word override:
# "Heritage Christian University" and "Revive College Church" are churches.
RELIGIOUS_WORD = _rx(['church', 'chapel', 'christian', 'ministry', 'ministries'])
# Research institutions only: a plain "St. Joseph Hospital" IS a Catholic
# hospital; "St. Jude Children's Research Hospital" is the secular exception.
MEDICAL_OVERRIDE = _rx([
    'research',
])

# --- 5. Secular override -------------------------------------------------
SECULAR = _rx([
    'hospital', 'medical center', 'health system', 'healthcare',
    'public library', 'community foundation', 'united way', 'humane society',
    'spca', 'animal shelter', 'food bank', 'chamber of commerce', 'rotary',
    'kiwanis', 'lions club', 'symphony', 'orchestra', 'philharmonic',
    'opera', 'ballet', 'museum', 'zoo', 'aquarium', 'botanical', 'arboretum',
    'nature conservancy', 'sierra club', 'audubon', 'planned parenthood',
    'aclu', 'human rights campaign', 'public television', 'public radio',
    'pbs ', 'npr ', 'boys and girls club', 'big brothers', 'big sisters',
    'girl scouts', '4-h', 'little league', 'special olympics', 'make-a-wish',
    'red cross', 'american cancer', 'heart association', 'diabetes association',
    'march of dimes', "alzheimer's", 'ronald mcdonald', 'university',
    'college', 'institute of technology', 'school district', 'public schools',
    'chamber orchestra', 'historical society', 'land trust', 'conservancy',
])
# Salvation Army is Christian even though "army"/service-like — never secular.
SALVATION_ARMY = _rx(['salvation army'])

# Placeholder / non-recipient text (990-PF grant schedules often list
# attachments, "various", or patient-assistance categories instead of named
# orgs). These are not identifiable Christian recipients -> non-Christian,
# which keeps the Christian percentage honest and raises coverage.
PLACEHOLDER = re.compile(
    r'^\s*('
    r'various|see\s+(attached|statement|schedule|attachment|below|list|note)'
    r'|attached|atch\b|stmt|statement\s*\d|schedule\s*\d|exhibit'
    r'|individual[s]?|eligible\s+patient|needy\s+(patient|individual|famil)'
    r'|individual\s+patient|patient\s+(program|assistance|group)'
    r'|anonymous|confidential|withheld|not\s+applicable|n\s*/?\s*a\b'
    r'|hip+a|multiple|numerous|no\s+name|name\s+withheld|donation[s]?'
    r'|grant[s]?|contribution[s]?|misc|other|general|unknown|none'
    r')\b', re.IGNORECASE)

# Large secular funders/recipients that recur at high dollar volume.
BIG_SECULAR = _rx([
    'gates foundation', 'bill & melinda gates', 'bill and melinda gates',
    'kellogg foundation', 'rockefeller', 'ford foundation', 'gavi',
    'global fund', 'world health organization', 'new venture fund',
    'tony blair', 'path foundation', 'wellcome', 'bloomberg',
    'silicon valley community', 'fidelity investments charitable',
    'schwab charitable', 'donors trust', 'vanguard charitable',
    'american online giving', 'network for good', 'clinton foundation',
])


def tradition(name: str) -> str | None:
    """For a Christian recipient, return which branch matched — a subtle
    display hint. Returns 'Catholic' | 'Orthodox' | 'Evangelical/Protestant'
    | None. Only meaningful when classify() returns 'christian'."""
    if not name:
        return None
    n = f' {name.lower().strip()} '
    # An explicit Protestant denomination beats saint/Catholic vocabulary.
    if PROT_DENOMINATION.search(n):
        return 'Evangelical/Protestant'
    # Orthodox markers beat the Catholic saint/monastery vocabulary.
    if ORTHODOX.search(n):
        return 'Orthodox'
    if CATHOLIC.search(n) and not BBBS.search(n):
        return 'Catholic'
    if (SALVATION_ARMY.search(n) or MESSIANIC.search(n)
            or PROTESTANT.search(n)):
        return 'Evangelical/Protestant'
    if SAINT.search(n) and not SAINT_PLACE.search(n):
        return 'Catholic'
    return None


def classify(name: str) -> str | None:
    """Return 'christian' | 'nonchristian' | None (uncategorized)."""
    if not name:
        return None
    raw = name.strip()
    n = f' {raw.lower()} '

    # placeholder / non-recipient text -> not an identifiable Christian org
    if PLACEHOLDER.match(raw) or len(raw) <= 2:
        return 'nonchristian'

    if SALVATION_ARMY.search(n):
        return 'christian'
    if MESSIANIC.search(n):
        return 'christian'
    if BIG_SECULAR.search(n) and not PROTESTANT.search(n):
        return 'nonchristian'
    # exclusions first
    for rx in (JEWISH, CHRISTIAN_SCIENCE, MORMON, JW, UNITARIAN, MUSLIM,
               OTHER_RELIGION):
        if rx.search(n):
            return 'nonchristian'
    # "Big Brothers Big Sisters" must not fall into Catholic 'sisters of'.
    if BBBS.search(n):
        return 'nonchristian'
    if (CATHOLIC.search(n) or ORTHODOX.search(n)):
        return 'christian'
    if PROTESTANT.search(n):
        return 'christian'
    # saint names -> Catholic, unless the "St" is a street/state/place name
    # or a medical/research override with no other Christian signal applies
    if SAINT.search(n) and not SAINT_PLACE.search(n):
        if MEDICAL_OVERRIDE.search(n) and not PROTESTANT.search(n):
            return 'nonchristian'
        return 'christian'
    # ambiguous words need a co-occurring Christian signal
    if AMBIGUOUS.search(n) and CHRISTIAN_SIGNAL.search(n):
        return 'christian'
    # secular override — blocked by an explicit religious word in the name
    # ("Heritage Christian University", "Revive College Church" are churches)
    if SECULAR.search(n):
        if RELIGIOUS_WORD.search(n):
            return 'christian'
        return 'nonchristian'
    return None
