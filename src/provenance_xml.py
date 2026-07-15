"""Small namespace-independent XML primitives shared by rebuild parsers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from lxml import etree


def local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def first_descendant(element: etree._Element | None, name: str):
    if element is None:
        return None
    return next((item for item in element.iter() if local_name(item) == name), None)


def child(element: etree._Element | None, name: str):
    if element is None:
        return None
    return next((item for item in element if local_name(item) == name), None)


def text(element: etree._Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def descendant_text(element: etree._Element | None, *names: str) -> str:
    if element is None:
        return ""
    for name in names:
        value = text(first_descendant(element, name))
        if value:
            return value
    return ""


def child_text(element: etree._Element | None, *names: str) -> str:
    for name in names:
        value = text(child(element, name))
        if value:
            return value
    return ""


def parse_integer(raw: str) -> tuple[int | None, str]:
    """Preserve missing, invalid, zero, negative, and positive distinctly."""
    if not raw:
        return None, "missing"
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None, "invalid"
    if not value.is_finite() or value != value.to_integral_value():
        return None, "invalid"
    amount = int(value)
    if amount > 0:
        return amount, "positive"
    if amount < 0:
        return amount, "negative"
    return 0, "zero"


def nullable_integer(root: etree._Element, *names: str) -> int | None:
    amount, status = parse_integer(descendant_text(root, *names))
    return amount if status != "invalid" else None


def normalize_timestamp(raw: str) -> str | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except ValueError:
        return None


def address_fields(group: etree._Element) -> dict[str, Any]:
    # 990-PF grant and application blocks nest the address under
    # RecipientUSAddress / RecipientForeignAddress; the bare USAddress /
    # ForeignAddress names only appear on the filer header. The original
    # exact-name lookup missed the Recipient* variants, silently blanking
    # city/state/country on all 5.1M grant rows.
    us = first_descendant(group, "RecipientUSAddress")
    if us is None:
        us = first_descendant(group, "USAddress")
    foreign = first_descendant(group, "RecipientForeignAddress")
    if foreign is None:
        foreign = first_descendant(group, "ForeignAddress")
    source = us if us is not None else foreign
    is_foreign = int(us is None and foreign is not None)
    return {
        "recipient_city": child_text(source, "CityNm", "City"),
        "recipient_state": child_text(source, "StateAbbreviationCd", "State", "ProvinceOrStateNm"),
        "recipient_country": (
            "US" if us is not None else child_text(source, "CountryCd", "CountryNm")
        ),
        "is_foreign": is_foreign,
    }
