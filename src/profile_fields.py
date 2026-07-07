"""Extract Phase 2 profile fields from a 990-PF XML root.

Fields: website, phone, revenue, Part XIV line 2 (invite-only) and the
2a-2d application block (contact person/address/phone/email, format,
deadlines, restrictions).
"""

import re

WEBSITE_BLANKS = frozenset(['N/A', 'NA', 'NONE', 'NOT APPLICABLE', 'N.A.'])


def _text(root, xpath, ns):
    el = root.find(xpath, ns)
    return el.text.strip() if el is not None and el.text else ''


def format_phone(raw: str) -> str:
    """Format a 10-digit US phone as (XXX) XXX-XXXX; pass through others."""
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw or ''


def normalize_website(raw: str) -> str:
    val = (raw or '').strip()
    if val.upper() in WEBSITE_BLANKS:
        return ''
    return val


# Never surface the paid preparer's phone as the foundation's number
PREPARER_BLOCKS = frozenset([
    'PreparerPersonGrp', 'PreparerFirmGrp', 'PaidPreparerInformationGrp',
])


def _foundation_phone(root, ns) -> str:
    """Filer phone, else officer/books-in-care-of phone (not preparer)."""
    for xp in ('.//irs:Filer/irs:PhoneNum',
               './/irs:BusinessOfficerGrp/irs:PhoneNum'):
        val = _text(root, xp, ns)
        if val:
            return val
    for el in root.iter(f"{{{ns['irs']}}}PhoneNum"):
        ancestors = {a.tag.split('}')[-1] for a in el.iterancestors()}
        if not ancestors & PREPARER_BLOCKS:
            return el.text.strip() if el.text else ''
    return ''


def _contact_address(grp, ns) -> str:
    """Join a Recipient US or foreign address into one display string."""
    for kind in ('irs:RecipientUSAddress', 'irs:RecipientForeignAddress'):
        addr = grp.find(kind, ns)
        if addr is None:
            continue
        parts = [
            _text(addr, 'irs:AddressLine1Txt', ns),
            _text(addr, 'irs:AddressLine2Txt', ns),
            _text(addr, 'irs:CityNm', ns),
            _text(addr, 'irs:StateAbbreviationCd', ns)
            or _text(addr, 'irs:ProvinceOrStateNm', ns),
            _text(addr, 'irs:ZIPCd', ns)
            or _text(addr, 'irs:ForeignPostalCd', ns),
            _text(addr, 'irs:CountryCd', ns),
        ]
        return ', '.join(p for p in parts if p)
    return ''


def extract_profile_fields(root, ns) -> dict:
    """Return the Phase 2 field dict for one parsed 990-PF."""
    invite_only = (
        _text(root, './/irs:OnlyContriToPreselectedInd', ns)
        .strip().upper() == 'X'
    )

    fields = {
        'website': normalize_website(
            _text(root, './/irs:WebsiteAddressTxt', ns)
        ),
        'phone': format_phone(_foundation_phone(root, ns)),
        'revenue': None,
        'invite_only': 1 if invite_only else 0,
        'contact_person': '',
        'contact_address': '',
        'contact_phone': '',
        'contact_email': '',
        'application_format': '',
        'deadlines': '',
        'restrictions': '',
        'has_application_info': 0,
    }

    revenue_txt = _text(root, './/irs:TotalRevAndExpnssAmt', ns)
    try:
        fields['revenue'] = int(float(revenue_txt)) if revenue_txt else None
    except (ValueError, TypeError):
        pass

    grp = root.find('.//irs:ApplicationSubmissionInfoGrp', ns)
    if grp is not None:
        fields.update({
            'contact_person': _text(grp, 'irs:RecipientPersonNm', ns),
            'contact_address': _contact_address(grp, ns),
            'contact_phone': format_phone(
                _text(grp, 'irs:RecipientPhoneNum', ns)
            ),
            'contact_email': _text(grp, 'irs:RecipientEmailAddressTxt', ns),
            'application_format': _text(
                grp, 'irs:FormAndInfoAndMaterialsTxt', ns
            ),
            'deadlines': _text(grp, 'irs:SubmissionDeadlinesTxt', ns),
            'restrictions': _text(grp, 'irs:RestrictionsOnAwardsTxt', ns),
            'has_application_info': 1,
        })

    return fields


# De facto invite-only / relationship-driven language that appears even when
# the Part XIV line-2 checkbox is left unchecked (e.g. Maclellan).
_INVITE_TEXT = re.compile(
    r'no unsolicited|not accept unsolicited|does not accept (unsolicited|'
    r'application)|not accepting|by invitation|invitation only|preselected|'
    r'pre-selected|pre-determined|predetermined|initiated by (the )?(found|'
    r'trust|donor)|does not consider unsolicited|not solicit', re.IGNORECASE)
_CONTACT_FIRST = re.compile(
    r'upon (contact|request)|contacting|by (telephone|phone|referral)|'
    r'must (first )?contact|provided upon|will be provided|by referral only',
    re.IGNORECASE)


def application_status(invite_only: int, has_application_info: int,
                       fmt: str = '', restrictions: str = '',
                       deadlines: str = '') -> str:
    """Derive a customer-facing status from Part XIV.

    Beyond the line-2 checkbox, scan the 2a-2d free text: many foundations
    leave the checkbox unchecked but describe a relationship-driven /
    'contact first' process, which is not the same as open applications.
    """
    if invite_only:
        return 'Invite Only'
    blob = f'{fmt} {restrictions} {deadlines}'
    if _INVITE_TEXT.search(blob):
        return 'Invite Only'
    if has_application_info:
        if _CONTACT_FIRST.search(blob):
            return 'Contact First'
        return 'Accepting Applications'
    return ''


PROFILE_COLUMNS = [
    'website', 'phone', 'revenue', 'invite_only', 'contact_person',
    'contact_address', 'contact_phone', 'contact_email',
    'application_format', 'deadlines', 'restrictions',
    'has_application_info',
]
