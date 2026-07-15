from __future__ import annotations

import sqlite3
from pathlib import Path

from src.parser import create_tables as create_legacy_tables
from src.provenance_parser import parse_file
from src.provenance_schema import canonicalize_filings, create_schema
from src.rebuild_database import insert_result

XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Return xmlns="http://www.irs.gov/efile">
  <ReturnHeader>
    <ReturnTs>{timestamp}</ReturnTs>
    <TaxPeriodEndDt>2023-12-31</TaxPeriodEndDt>
    <ReturnTypeCd>{return_type}</ReturnTypeCd>
    <Filer>
      <EIN>123456789</EIN>
      <BusinessName><BusinessNameLine1Txt>TEST FOUNDATION</BusinessNameLine1Txt></BusinessName>
      <USAddress><CityNm>ATLANTA</CityNm><StateAbbreviationCd>GA</StateAbbreviationCd></USAddress>
      <PhoneNum>4045550100</PhoneNum>
    </Filer>
  </ReturnHeader>
  <ReturnData>
    <IRS990PF>
      <TaxYr>2023</TaxYr>
      {amended}
      <FMVAssetsEOYAmt>900000</FMVAssetsEOYAmt>
      <QualifyingDistributionsAmt>125000</QualifyingDistributionsAmt>
      <GrantOrContributionPdDurYrGrp>
        <RecipientBusinessName>
          <BusinessNameLine1Txt>PAID MINISTRY</BusinessNameLine1Txt>
        </RecipientBusinessName>
        <RecipientUSAddress>
          <CityNm>MACON</CityNm><StateAbbreviationCd>GA</StateAbbreviationCd>
        </RecipientUSAddress>
        <Amt>100000</Amt>
        <GrantOrContributionPurposeTxt>PROGRAM SUPPORT</GrantOrContributionPurposeTxt>
      </GrantOrContributionPdDurYrGrp>
      <GrantOrContributionPdDurYrGrp>
        <RecipientPersonNm>ZERO ADJUSTMENT</RecipientPersonNm><Amt>0</Amt>
      </GrantOrContributionPdDurYrGrp>
      <GrantOrContributionPdDurYrGrp>
        <RecipientPersonNm>NEGATIVE ADJUSTMENT</RecipientPersonNm><Amt>-5000</Amt>
      </GrantOrContributionPdDurYrGrp>
      <GrantOrContriApprvForFutGrp>
        <RecipientBusinessName>
          <BusinessNameLine1Txt>FUTURE MINISTRY</BusinessNameLine1Txt>
        </RecipientBusinessName>
        <Amt>250000</Amt>
      </GrantOrContriApprvForFutGrp>
    </IRS990PF>
  </ReturnData>
</Return>
"""


def write_xml(
    path: Path,
    *,
    timestamp: str = "2024-02-01T12:00:00-05:00",
    amended: bool = False,
    return_type: str = "990PF",
) -> Path:
    path.write_text(
        XML_TEMPLATE.format(
            timestamp=timestamp,
            amended="<AmendedReturnInd>X</AmendedReturnInd>" if amended else "",
            return_type=return_type,
        ),
        encoding="utf-8",
    )
    return path


def test_parser_preserves_schedule_and_signed_amount_status(tmp_path: Path) -> None:
    parsed = parse_file(str(write_xml(tmp_path / "111_public.xml")))
    assert parsed["filing"]["parse_status"] == "parsed"
    assert parsed["foundation"]["qualifying_distributions"] == 125_000
    assert [grant["schedule_type"] for grant in parsed["grants"]] == [
        "paid",
        "paid",
        "paid",
        "future_approved",
    ]
    assert [grant["amount_status"] for grant in parsed["grants"]] == [
        "positive",
        "zero",
        "negative",
        "positive",
    ]
    assert parsed["grants"][2]["signed_amount"] == -5_000


def test_non_pf_return_is_retained_but_excluded(tmp_path: Path) -> None:
    parsed = parse_file(str(write_xml(tmp_path / "222_public.xml", return_type="990")))
    assert parsed["filing"]["parse_status"] == "excluded_return_type"
    assert parsed["foundation"] is None
    assert parsed["grants"] == []


def test_canonical_policy_selects_latest_return_and_paid_view(tmp_path: Path) -> None:
    first = parse_file(
        str(write_xml(tmp_path / "333_public.xml", timestamp="2024-01-01T12:00:00-05:00"))
    )
    amended = parse_file(
        str(
            write_xml(
                tmp_path / "444_public.xml", timestamp="2024-03-01T12:00:00-05:00", amended=True
            )
        )
    )
    conn = sqlite3.connect(tmp_path / "rebuilt.db")
    create_schema(conn)
    insert_result(conn, first)
    insert_result(conn, amended)
    conn.commit()
    assert canonicalize_filings(conn) == 1
    assert conn.execute("SELECT object_id FROM canonical_filings").fetchone()[0] == "444"
    assert conn.execute("SELECT COUNT(*) FROM paid_grants").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM paid_adjustments").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM future_approved_grants").fetchone()[0] == 1
    conn.close()


def test_legacy_migration_does_not_mark_unknown_rows_paid() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE grants (id INTEGER PRIMARY KEY, ein TEXT, tax_year INTEGER)")
    conn.execute("INSERT INTO grants(ein, tax_year) VALUES ('123456789', 2023)")
    create_legacy_tables(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(grants)")}
    assert "schedule_type" in columns
    assert conn.execute("SELECT schedule_type FROM grants").fetchone()[0] == "unclassified"
    conn.close()


ADDRESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Return xmlns="http://www.irs.gov/efile">
  <ReturnHeader>
    <ReturnTs>2024-02-01T12:00:00-05:00</ReturnTs>
    <TaxPeriodEndDt>2023-12-31</TaxPeriodEndDt>
    <ReturnTypeCd>990PF</ReturnTypeCd>
    <Filer>
      <EIN>987654321</EIN>
      <BusinessName><BusinessNameLine1Txt>ADDR TEST FDN</BusinessNameLine1Txt></BusinessName>
      <USAddress><CityNm>DALLAS</CityNm><StateAbbreviationCd>TX</StateAbbreviationCd></USAddress>
    </Filer>
  </ReturnHeader>
  <ReturnData>
    <IRS990PF>
      <TaxYr>2023</TaxYr>
      <GrantOrContributionPdDurYrGrp>
        <RecipientBusinessName>
          <BusinessNameLine1Txt>HERITAGE VALLEY HEALTH SYSTEM</BusinessNameLine1Txt>
          <BusinessNameLine2Txt>FOUNDATION</BusinessNameLine2Txt>
        </RecipientBusinessName>
        <RecipientUSAddress>
          <AddressLine1Txt>420 ROUSER ROAD</AddressLine1Txt>
          <CityNm>MOON TOWNSHIP</CityNm>
          <StateAbbreviationCd>PA</StateAbbreviationCd>
          <ZIPCd>15108</ZIPCd>
        </RecipientUSAddress>
        <RecipientFoundationStatusTxt>PC</RecipientFoundationStatusTxt>
        <GrantOrContributionPurposeTxt>GENERAL SUPPORT</GrantOrContributionPurposeTxt>
        <Amt>17037</Amt>
      </GrantOrContributionPdDurYrGrp>
      <GrantOrContributionPdDurYrGrp>
        <RecipientBusinessName>
          <BusinessNameLine1Txt>OVERSEAS MISSION</BusinessNameLine1Txt>
        </RecipientBusinessName>
        <RecipientForeignAddress>
          <CityNm>NAIROBI</CityNm><CountryCd>KE</CountryCd>
        </RecipientForeignAddress>
        <Amt>25000</Amt>
      </GrantOrContributionPdDurYrGrp>
    </IRS990PF>
  </ReturnData>
</Return>
"""


def test_parser_extracts_recipient_address_and_status(tmp_path: Path) -> None:
    """Regression: RecipientUSAddress fields were silently blanked on all rows."""
    path = tmp_path / "222_public.xml"
    path.write_text(ADDRESS_XML, encoding="utf-8")
    grants = parse_file(str(path))["grants"]
    domestic, foreign = grants
    assert domestic["recipient_name"] == "HERITAGE VALLEY HEALTH SYSTEM FOUNDATION"
    assert domestic["recipient_city"] == "MOON TOWNSHIP"
    assert domestic["recipient_state"] == "PA"
    assert domestic["recipient_country"] == "US"
    assert domestic["recipient_foundation_status"] == "PC"
    assert domestic["is_foreign"] == 0
    assert foreign["recipient_city"] == "NAIROBI"
    assert foreign["recipient_country"] == "KE"
    assert foreign["is_foreign"] == 1
