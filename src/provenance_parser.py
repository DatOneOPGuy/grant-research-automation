"""Namespace-tolerant, provenance-preserving IRS XML parser."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lxml import etree

from src.provenance_schema import SCHEMA_VERSION
from src.provenance_xml import (
    address_fields,
    child_text,
    descendant_text,
    first_descendant,
    local_name,
    normalize_timestamp,
    nullable_integer,
    parse_integer,
)

GRANT_GROUPS = {
    "GrantOrContributionPdDurYrGrp": ("paid", ".//irs:GrantOrContributionPdDurYrGrp"),
    "GrantOrContriPaidDuringYear": ("paid", ".//irs:GrantOrContriPaidDuringYear"),
    "GrantOrContriApprvForFutGrp": ("future_approved", ".//irs:GrantOrContriApprvForFutGrp"),
}


def object_id_from_path(path: str | Path) -> str:
    return Path(path).stem.removesuffix("_public")


def recipient_name(group: etree._Element) -> str:
    business = first_descendant(group, "RecipientBusinessName")
    if business is not None:
        parts = [
            child_text(business, "BusinessNameLine1Txt", "BusinessNameLine1"),
            child_text(business, "BusinessNameLine2Txt", "BusinessNameLine2"),
        ]
        value = " ".join(part for part in parts if part)
        if value:
            return value
    return descendant_text(group, "RecipientPersonNm")


def parse_grants(root: etree._Element, object_id: str, ein: str, tax_year: int):
    grants = []
    ordinal = 0
    for group in root.iter():
        group_name = local_name(group)
        if group_name not in GRANT_GROUPS:
            continue
        ordinal += 1
        schedule_type, source_xpath = GRANT_GROUPS[group_name]
        amount_text = descendant_text(group, "Amt", "GrantOrContributionAmt", "Amount")
        signed_amount, amount_status = parse_integer(amount_text)
        grant = {
            "grant_id": f"{object_id}:{ordinal:07d}",
            "object_id": object_id,
            "ein": ein,
            "tax_year": tax_year,
            "schedule_type": schedule_type,
            "source_xpath": source_xpath,
            "row_ordinal": ordinal,
            "recipient_name": recipient_name(group),
            "recipient_ein_raw": descendant_text(group, "RecipientEIN"),
            # PC/PF/NC/etc. as reported by the filer — cheap to capture now,
            # and it targets the recipient-990 pull (PC recipients file 990s).
            "recipient_foundation_status": descendant_text(
                group, "RecipientFoundationStatusTxt"
            ),
            "amount_text": amount_text,
            "signed_amount": signed_amount,
            "amount_status": amount_status,
            "purpose": descendant_text(group, "GrantOrContributionPurposeTxt", "PurposeTxt"),
        }
        grant.update(address_fields(group))
        grants.append(grant)
    return grants


def contact_address(group: etree._Element) -> str:
    fields = address_fields(group)
    parts = [
        descendant_text(group, "AddressLine1Txt", "AddressLine1"),
        descendant_text(group, "AddressLine2Txt", "AddressLine2"),
        fields["recipient_city"],
        fields["recipient_state"],
        descendant_text(group, "ZIPCd", "ForeignPostalCd"),
        fields["recipient_country"] if fields["is_foreign"] else "",
    ]
    return ", ".join(part for part in parts if part)


def foundation_phone(root: etree._Element) -> str:
    for group_name in ("Filer", "BusinessOfficerGrp"):
        group = first_descendant(root, group_name)
        value = descendant_text(group, "PhoneNum") if group is not None else ""
        if value:
            return value
    return ""


def application_fields(application: etree._Element | None) -> dict:
    if application is None:
        return {
            "contact_person": "",
            "contact_address": "",
            "contact_phone": "",
            "contact_email": "",
            "application_format": "",
            "deadlines": "",
            "restrictions": "",
            "has_application_info": 0,
        }
    return {
        "contact_person": descendant_text(application, "RecipientPersonNm"),
        "contact_address": contact_address(application),
        "contact_phone": descendant_text(application, "RecipientPhoneNum"),
        "contact_email": descendant_text(application, "RecipientEmailAddressTxt"),
        "application_format": descendant_text(application, "FormAndInfoAndMaterialsTxt"),
        "deadlines": descendant_text(application, "SubmissionDeadlinesTxt"),
        "restrictions": descendant_text(application, "RestrictionsOnAwardsTxt"),
        "has_application_info": 1,
    }


def parse_foundation(root: etree._Element, object_id: str, ein: str, tax_year: int):
    filer = first_descendant(root, "Filer")
    name_group = first_descendant(filer, "BusinessName") if filer is not None else None
    name = " ".join(
        part
        for part in (
            child_text(name_group, "BusinessNameLine1Txt", "BusinessNameLine1"),
            child_text(name_group, "BusinessNameLine2Txt", "BusinessNameLine2"),
        )
        if part
    )
    address = first_descendant(filer, "USAddress") if filer is not None else None
    foreign = first_descendant(filer, "ForeignAddress") if filer is not None else None
    source = address if address is not None else foreign
    application = first_descendant(root, "ApplicationSubmissionInfoGrp")
    invite = descendant_text(root, "OnlyContriToPreselectedInd").upper() == "X"
    profile = {
        "object_id": object_id,
        "ein": ein,
        "tax_year": tax_year,
        "organization_name": name,
        "city": child_text(source, "CityNm", "City"),
        "state": child_text(source, "StateAbbreviationCd", "State", "ProvinceOrStateNm"),
        "country": "US" if address is not None else child_text(source, "CountryCd", "CountryNm"),
        "assets_eoy": nullable_integer(root, "FMVAssetsEOYAmt", "TotalAssetsEOYAmt"),
        "qualifying_distributions": nullable_integer(root, "QualifyingDistributionsAmt"),
        "contributions_paid": nullable_integer(root, "ContriPaidRevAndExpnssAmt"),
        "total_revenue": nullable_integer(root, "TotalRevAndExpnssAmt"),
        "website": descendant_text(root, "WebsiteAddressTxt"),
        "phone": foundation_phone(root),
        "invite_only": int(invite),
    }
    profile.update(application_fields(application))
    return profile


def filing_record(root: etree._Element, path: Path, digest: str, metadata: dict):
    object_id = object_id_from_path(path)
    raw_timestamp = descendant_text(root, "ReturnTs")
    tax_year_raw = descendant_text(root, "TaxYr", "TaxYear")
    ein = descendant_text(first_descendant(root, "Filer"), "EIN")
    return {
        "object_id": object_id,
        "source_path": str(path),
        "source_sha256": digest,
        "return_id": metadata.get("RETURN_ID"),
        "filing_type": metadata.get("FILING_TYPE"),
        "index_year": metadata.get("index_year"),
        "index_tax_period": metadata.get("TAX_PERIOD"),
        "index_return_type": metadata.get("RETURN_TYPE"),
        "dln": metadata.get("DLN"),
        "xml_batch_id": metadata.get("XML_BATCH_ID"),
        "ein": ein,
        "return_type": descendant_text(root, "ReturnTypeCd"),
        "tax_year": int(tax_year_raw) if tax_year_raw.isdigit() else None,
        "tax_period_end": descendant_text(root, "TaxPeriodEndDt"),
        "return_timestamp_raw": raw_timestamp,
        "return_timestamp_utc": normalize_timestamp(raw_timestamp),
        "is_amended": int(descendant_text(root, "AmendedReturnInd").upper() == "X"),
        "parser_version": SCHEMA_VERSION,
        "parse_status": "parsed",
        "error_message": None,
        "parsed_at_utc": datetime.now(UTC).isoformat(),
    }


def parse_file(path_text: str, metadata: dict | None = None) -> dict[str, Any]:
    """Parse one XML into filing, foundation, and grant records."""
    path = Path(path_text)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    metadata = metadata or {}
    try:
        root = etree.fromstring(
            payload,
            parser=etree.XMLParser(
                resolve_entities=False, no_network=True, recover=False, huge_tree=True
            ),
        )
        filing = filing_record(root, path, digest, metadata)
        if filing["return_type"] != "990PF":
            filing["parse_status"] = "excluded_return_type"
            return {"filing": filing, "foundation": None, "grants": []}
        if not filing["ein"] or not filing["tax_year"]:
            filing["parse_status"] = "invalid_identity"
            return {"filing": filing, "foundation": None, "grants": []}
        foundation = parse_foundation(root, filing["object_id"], filing["ein"], filing["tax_year"])
        grants = parse_grants(root, filing["object_id"], filing["ein"], filing["tax_year"])
        return {"filing": filing, "foundation": foundation, "grants": grants}
    except (OSError, etree.XMLSyntaxError, ValueError) as error:
        filing = error_filing(path, digest, metadata, error)
        return {"filing": filing, "foundation": None, "grants": []}


def error_filing(path: Path, digest: str, metadata: dict, error: Exception):
    """Retain failed source provenance so errors cannot disappear silently."""
    return {
        "object_id": object_id_from_path(path),
        "source_path": str(path),
        "source_sha256": digest,
        "return_id": metadata.get("RETURN_ID"),
        "filing_type": metadata.get("FILING_TYPE"),
        "index_year": metadata.get("index_year"),
        "index_tax_period": metadata.get("TAX_PERIOD"),
        "index_return_type": metadata.get("RETURN_TYPE"),
        "dln": metadata.get("DLN"),
        "xml_batch_id": metadata.get("XML_BATCH_ID"),
        "ein": metadata.get("EIN"),
        "return_type": None,
        "tax_year": None,
        "tax_period_end": None,
        "return_timestamp_raw": None,
        "return_timestamp_utc": None,
        "is_amended": 0,
        "parser_version": SCHEMA_VERSION,
        "parse_status": "parse_error",
        "error_message": f"{type(error).__name__}: {str(error)[:400]}",
        "parsed_at_utc": datetime.now(UTC).isoformat(),
    }
