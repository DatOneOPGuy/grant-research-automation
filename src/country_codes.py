"""Country codes as they actually appear in 990-PF filings.

The IRS instructs filers to use FIPS 10-4 / State Department two-letter codes,
NOT ISO 3166. The two disagree in ways that silently invert geography:

    SZ  FIPS Switzerland   ISO Eswatini
    CH  FIPS China         ISO Switzerland
    NI  FIPS Nigeria       ISO Nicaragua
    IS  FIPS Israel        ISO Iceland
    GM  FIPS Germany       ISO Gambia
    MA  FIPS Madagascar    ISO Morocco
    PA  FIPS Paraguay      ISO Panama
    SG  FIPS Senegal       ISO Singapore

Reading these as ISO would report $3.4B of Swiss grantmaking as Eswatini. So
every mapping below was verified against the recipient city text in the filings
themselves -- Geneva/Zurich for SZ, Beijing/Shanghai for CH, Abuja/Lagos for
NI -- rather than taken from a code table on faith. `logs/country_codes.md`
records that check.

Two deliberate departures from FIPS, both driven by what the city text shows:

  * GB -> United Kingdom. FIPS GB is Gabon, but filers overwhelmingly use GB
    as the ISO code for Great Britain; the cities are London, Aberdeen,
    Glasgow, Bristol. Gabon files under GB's FIPS neighbour and is not
    otherwise represented.
  * OC -> unmapped. Not a valid code in either standard. Its cities scatter
    across London, Pristina, Ramallah and Juba, so it is a filer catch-all
    meaning "somewhere else", and is surfaced as Unspecified rather than
    guessed.

AMBIGUOUS holds codes whose city text contradicts FIPS but whose volume is too
small to establish intent (single-digit mentions, near-zero dollars). They are
labelled as unverified rather than assigned, because a confidently wrong
country is worse for a researcher than an admitted unknown.
"""

from __future__ import annotations

# FIPS 10-4, verified against filing city text. Value is the display name.
FIPS: dict[str, str] = {
    "AA": "Aruba", "AC": "Antigua and Barbuda", "AE": "United Arab Emirates",
    "AF": "Afghanistan", "AG": "Algeria", "AJ": "Azerbaijan", "AL": "Albania",
    "AM": "Armenia", "AO": "Angola", "AQ": "American Samoa",
    "AR": "Argentina", "AS": "Australia", "AU": "Austria", "AV": "Anguilla",
    "BA": "Bahrain", "BB": "Barbados", "BC": "Botswana", "BD": "Bermuda",
    "BE": "Belgium", "BF": "Bahamas", "BG": "Bangladesh", "BH": "Belize",
    "BK": "Bosnia and Herzegovina", "BL": "Bolivia", "BM": "Myanmar",
    "BN": "Benin", "BO": "Belarus", "BP": "Solomon Islands", "BR": "Brazil",
    "BT": "Bhutan", "BU": "Bulgaria", "BY": "Burundi", "CA": "Canada",
    "CB": "Cambodia", "CD": "Chad", "CE": "Sri Lanka",
    "CF": "Congo (Brazzaville)", "CG": "Congo (Kinshasa)", "CH": "China",
    "CI": "Chile", "CJ": "Cayman Islands", "CM": "Cameroon", "CN": "Comoros",
    "CO": "Colombia", "CQ": "Northern Mariana Islands", "CS": "Costa Rica",
    "CT": "Central African Republic", "CU": "Cuba", "CV": "Cabo Verde",
    "CY": "Cyprus", "DA": "Denmark", "DO": "Dominica",
    "DR": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt",
    "EI": "Ireland", "EK": "Equatorial Guinea", "EN": "Estonia",
    "ER": "Eritrea", "ES": "El Salvador", "ET": "Ethiopia", "EZ": "Czechia",
    "FI": "Finland", "FJ": "Fiji", "FM": "Micronesia", "FO": "Faroe Islands",
    "FP": "French Polynesia", "FR": "France", "GA": "Gambia", "GG": "Georgia",
    "GH": "Ghana", "GI": "Gibraltar", "GJ": "Grenada", "GM": "Germany",
    "GQ": "Guam", "GR": "Greece", "GT": "Guatemala", "GV": "Guinea",
    "GY": "Guyana", "HA": "Haiti", "HK": "Hong Kong", "HO": "Honduras",
    "HR": "Croatia", "HU": "Hungary", "IC": "Iceland", "ID": "Indonesia",
    "IM": "Isle of Man", "IN": "India", "IR": "Iran", "IS": "Israel",
    "IT": "Italy", "IV": "Côte d'Ivoire", "IZ": "Iraq", "JA": "Japan",
    "JE": "Jersey", "JM": "Jamaica", "JO": "Jordan", "JQ": "Johnston Atoll",
    "KE": "Kenya", "KG": "Kyrgyzstan", "KS": "South Korea", "KU": "Kuwait",
    "KV": "Kosovo", "KZ": "Kazakhstan", "LA": "Laos", "LE": "Lebanon",
    "LG": "Latvia", "LH": "Lithuania", "LI": "Liberia", "LO": "Slovakia",
    "LS": "Liechtenstein", "LT": "Lesotho", "LU": "Luxembourg",
    "LY": "Libya", "MA": "Madagascar", "MC": "Macau", "MD": "Moldova",
    "MG": "Mongolia", "MH": "Montserrat", "MI": "Malawi",
    "MJ": "Montenegro", "MK": "North Macedonia", "ML": "Mali",
    "MN": "Monaco", "MO": "Morocco", "MP": "Mauritius", "MR": "Mauritania",
    "MT": "Malta", "MV": "Maldives", "MX": "Mexico", "MY": "Malaysia",
    "MZ": "Mozambique", "NC": "New Caledonia", "NG": "Niger", "NI": "Nigeria",
    "NL": "Netherlands", "NO": "Norway", "NP": "Nepal", "NR": "Nauru",
    "NS": "Suriname", "NU": "Nicaragua", "NZ": "New Zealand",
    "OD": "South Sudan", "PA": "Paraguay", "PC": "Pitcairn Islands",
    "PE": "Peru", "PK": "Pakistan", "PL": "Poland", "PM": "Panama",
    "PO": "Portugal", "PP": "Papua New Guinea", "PS": "Palau",
    "PU": "Guinea-Bissau", "QA": "Qatar", "RI": "Serbia", "RO": "Romania",
    "RP": "Philippines", "RQ": "Puerto Rico", "RS": "Russia", "RW": "Rwanda",
    "SA": "Saudi Arabia", "SC": "Saint Kitts and Nevis", "SE": "Seychelles",
    "SF": "South Africa", "SG": "Senegal", "SI": "Slovenia",
    "SL": "Sierra Leone", "SM": "San Marino", "SN": "Singapore",
    "SO": "Somalia", "SP": "Spain", "ST": "Saint Lucia", "SU": "Sudan",
    "SW": "Sweden", "SY": "Syria", "SZ": "Switzerland",
    "TB": "Saint Barthélemy", "TD": "Trinidad and Tobago", "TH": "Thailand",
    "TI": "Tajikistan", "TK": "Turks and Caicos Islands", "TN": "Tonga",
    "TO": "Togo", "TS": "Tunisia", "TT": "Timor-Leste", "TU": "Türkiye",
    "TW": "Taiwan", "TZ": "Tanzania", "UC": "Curaçao", "UG": "Uganda",
    "UK": "United Kingdom", "UP": "Ukraine", "UV": "Burkina Faso",
    "UY": "Uruguay", "UZ": "Uzbekistan",
    "VC": "Saint Vincent and the Grenadines", "VE": "Venezuela",
    "VI": "British Virgin Islands", "VM": "Vietnam",
    "VQ": "U.S. Virgin Islands", "WA": "Namibia", "WI": "Western Sahara",
    "WS": "Samoa", "WZ": "Eswatini", "YM": "Yemen", "ZA": "Zambia",
    "ZI": "Zimbabwe",
}

# Departures from FIPS, justified by city text (see module docstring).
OVERRIDES: dict[str, str] = {"GB": "United Kingdom"}

# City text contradicts FIPS, volume too small to establish intent.
AMBIGUOUS: frozenset[str] = frozenset({
    "AN",   # FIPS Andorra / ISO Netherlands Antilles; city Corinaldo (Italy)
    "AX",   # not FIPS; ISO Åland
    "DX",   # not a country: UK sovereign base area
    "KN",   # FIPS North Korea / ISO St Kitts; city Seoul (South Korea)
    "KR",   # FIPS Kiribati / ISO South Korea; city Seoul
    "NE",   # FIPS Niue; cities Utrecht, The Hague (Netherlands)
    "PF",   # FIPS Paracel Islands / ISO French Polynesia
    "PG",   # FIPS Spratly Islands / ISO Papua New Guinea
})

# Filer catch-alls and domestic markers.
UNSPECIFIED: frozenset[str] = frozenset({"OC"})
DOMESTIC: frozenset[str] = frozenset({"US", "USA", "U.S.", "U.S", "UNITED STATES", ""})

# US territories: legally domestic, but a fundraiser researching international
# work usually wants them separated from the fifty states.
TERRITORIES: frozenset[str] = frozenset({"RQ", "VQ", "GQ", "CQ", "AQ"})


def normalize(code: str | None) -> str:
    return (code or "").strip().upper()


def is_domestic(code: str | None) -> bool:
    return normalize(code) in DOMESTIC


def country_name(code: str | None) -> str | None:
    """Display name, or None when the code cannot be trusted.

    None is a deliberate answer: it routes the row to "Unspecified" in the
    product instead of asserting a country we have not established.
    """
    key = normalize(code)
    if not key or key in DOMESTIC:
        return None
    if key in OVERRIDES:
        return OVERRIDES[key]
    if key in AMBIGUOUS or key in UNSPECIFIED:
        return None
    return FIPS.get(key)


def is_territory(code: str | None) -> bool:
    return normalize(code) in TERRITORIES


def resolvable(code: str | None) -> bool:
    """True when we can name the country. Used to report honest coverage."""
    return country_name(code) is not None
