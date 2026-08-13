# Alias tranche 2 — validated worklist

_2026-08-13. Read-only. NOTHING has been auto-resolved. Every proposal in the
parked queue was re-validated against the BMF before this list was written._

## The queue's own proposals are mostly wrong

500 rows / $27.918B. 341 carried a proposed EIN, but **only 36.5% of the
token-containment proposals survive validation** — the filed name's tokens are
not present in the proposed organisation's BMF name. The failures are not
subtle:

| filed name | dollars | proposed match |
|---|---:|---|
| WK Kellogg Foundation | $358,000,000 | KELLOGGSVILLE WARM-A-HEART |
| Schwab Charitable Fund | $256,501,253 | THE GEORGE SCHWAB AND LEONA LAUDER… |
| Columbia University | $245,030,807 | SUFFOLK COUNTY POLICE DEPT COLUMBIA… |
| Schwab Charitable Fund | $168,067,266 | SCHWAB DRIVE BAPTIST CHURCH |
| University of pennsylvania | $166,952,218 | PENNSYLVANIA CITIZENS FOR BETTER L… |
| Fidelity Charitable | $165,927,566 | FIDELITY HEALTH CARE INC |

Auto-resolving any of these would attach the wrong organisation's NTEE, mission
text and group ruling to hundreds of millions of dollars of giving. **This is
why the step was gated.**

## Disposition

| bucket | rows | dollars | action |
|---|---:|---:|---|
| SAFE — IRS truncation (abbreviation pairs) | 12 | $1.269B | auto-resolvable, listed below for audit |
| SAFE — token match + state agrees | 113 | $4.513B | auto-resolvable, listed below for audit |
| REVIEW — token match, state disagrees | 13 | $0.763B | **your call** |
| REJECT — fails token containment | 203 | $7.716B | discard the proposal, leave unresolved |
| NO CANDIDATE | 159 | $13.657B | no BMF match exists |

**Safely recoverable: 125 rows / $5.782B** — not the $14B the queue's proposal
count implied.

## 1. SAFE — IRS truncations (auto-resolvable, audit these)

| dollars | filed name | resolves to | EIN |
|---:|---|---|---|
| $1,001,387,051 | National Philanthropic Trust | NATIONAL PHILANTHROPIC TR | 237825575 |
| $53,690,000 | KOHLER TRUST FOR CLEAN WATER | KOHLER TR FOR CLEAN WATER | 326513655 |
| $50,030,000 | UNIVERSITY OF ILLINOIS FDN | UNIVERSITY OF ILLINOIS FOUNDATION | 376006007 |
| $30,200,000 | National Boy Scouts of America Fdn | NATIONAL BOY SCOUTS OF AMERICA FOUNDAT | 752675978 |
| $27,185,000 | Ichauway Incorporated | ICHAUWAY INC | 581824778 |
| $26,284,541 | Environmental Defense Fund Inc | ENVIRONMENTAL DEFENSE FUND INCORPORATE | 116107128 |
| $21,093,193 | Omaha Discovery Trust | OMAHA DISCOVERY TR | 320596113 |
| $12,695,872 | COMMUNITY FDN ALLIANCE INC | COMMUNITY FOUNDATION ALLIANCE INC | 351830262 |
| $12,070,725 | Deseret Trust Company | DESERET TRUST CO | 870291656 |
| $11,814,640 | UNIVERSITY OF MINNESOTA FDN | UNIVERSITY OF MINNESOTA FOUNDATION | 416042488 |
| $11,425,064 | UNIVERSITY OF CONNECTICUT FOUNDATION I | UNIVERSITY OF CONNECTICUT FOUNDATION I | 066070722 |
| $11,146,726 | World Central Kitchen inc | WORLD CENTRAL KITCHEN INCORPORATED | 273521132 |

## 2. SAFE — token match with state agreement (auto-resolvable, audit these)

| dollars | filed name | resolves to | city/state | EIN |
|---:|---|---|---|---|
| $354,909,807 | Michael J Fox Foundation for Parki | MICHAEL J FOX FOUNDATION FOR PARKI | NEW YORK, NY | 134141945 |
| $263,136,895 | Community Foundation for Greater A | THE COMMUNITY FOUNDATION FOR GREAT | ATLANTA, GA | 581344646 |
| $258,827,824 | Stanford university | CHI ALPHA CHRISTIAN FELLOWSHIP AT  | MENLO PARK, CA | 264580872 |
| $247,159,738 | University of Michigan | MICHIGAN STATE UNIVERSITY | ALPENA, MI | 010585619 |
| $233,889,228 | Massachusetts General Hospital | MASSACHUSETTS GENERAL HOSPITAL NUR | BOSTON, MA | 042121358 |
| $226,360,000 | ROTARY FOUNDATION OF ROTARY INTERN | THE ROTARY FOUNDATION OF ROTARY IN | EVANSTON, IL | 363245072 |
| $137,118,195 | brown university | BROWN UNIVERSITY OF PROVIDENCE | PROVIDENCE, RI | 050258809 |
| $99,385,398 | Environmental Defense Fund | ENVIRONMENTAL DEFENSE FUND INCORPO | NEW YORK, NY | 116107128 |
| $95,168,125 | INDIANA ASSOCIATION OF UNITED WAYS | INDIANA ASSOCIATION OF UNITED WAYS | INDIANAPOLIS, IN | 351441961 |
| $93,905,491 | Fidelity Charitable Gift Fund | FIDELITY INVESTMENTS CHARITABLE GI | BOSTON, MA | 110303001 |
| $77,176,898 | Jewish Community Foundation | JEWISH COMMUNITY FOUNDATION OF THE | LOS ANGELES, CA | 010734263 |
| $69,714,654 | Children's Healthcare of Atlanta | CHILDRENS HEALTHCARE OF ATLANTA IN | BROOKHAVEN, GA | 203962330 |
| $68,500,000 | PFIZER INC | PFIZER FOUNDATION INC | NEW YORK, NY | 136083839 |
| $68,067,581 | COMMONWEALTH FOUNDATION FOR CANCER | COMMONWEALTH FOUNDATION FOR CANCER | RICHMOND, VA | 043632101 |
| $61,252,845 | New York-Presbyterian Hospital | FOUNDATION OF NEW YORK-PRESBYTERIA | CORTLANDT MNR, NY | 133307781 |
| $60,914,994 | Seattle Children's Hospital | SEATTLE CHILDRENS HOSPITAL | SEATTLE, WA | 204541819 |
| $59,432,126 | Community Fdn of Greater Memphis | COMMUNITY FOUNDATION OF GREATER ME | MEMPHIS, TN | 581723645 |
| $53,876,440 | Dartmouth College | TRUSTEES OF DARTMOUTH COLLEGE | HANOVER, NH | 020222111 |
| $52,875,000 | ARMAND HAMMER UNITED WORLD COLLEGE | ARMAND HAMMER UNITED WORLD COLLEGE | MONTEZUMA, NM | 850297355 |
| $50,181,939 | BOARD OF TRUSTEES OF THE LELAND ST | THE BOARD OF TRUSTEES OF THE LELAN | REDWOOD CITY, CA | 941156365 |
| $48,270,720 | samaritan's purse | SAMARITANS PURSE | BOONE, NC | 581437002 |
| $45,900,000 | filing | LOUIS VIGIL SUBDIVISION FILING NO  | GOLDEN, CO | 371640588 |
| $42,257,902 | TASK FORCE FOR GLOBAL HEALTH INC T | THE TASK FORCE FOR GLOBAL HEALTH I | DECATUR, GA | 581698648 |
| $41,647,394 | The University of Texas at Dallas | UNIVERSITY OF NORTH TEXAS AT DALLA | DALLAS, TX | 453072303 |
| $39,515,402 | SCRIPPS RESEARCH INSTITUTE THE | SCRIPPS RESEARCH INSTITUTE | LA JOLLA, CA | 330435954 |
| $39,417,911 | Texas Children's Hospital | TEXAS CHILDRENS HOSPITAL FOUNDATIO | BELLAIRE, TX | 202380599 |
| $38,890,250 | World Central kitchen | WORLD CENTRAL KITCHEN INCORPORATED | WASHINGTON, DC | 273521132 |
| $34,944,203 | Children's Miracle Network | CHILDRENS MIRACLE NETWORK | SALT LAKE CTY, UT | 870387205 |
| $34,239,774 | Children's Hospital of Philadelphi | THE CHILDRENS HOSPITAL OF PHILADEL | PHILADELPHIA, PA | 231352166 |
| $33,859,597 | Brigham and Women's Hospital | PROFESSIONAL NURSES CHAPTER OF THE | CANTON, MA | 550916227 |
| $33,799,183 | Harlem Children's Zone | HARLEM CHILDRENS ZONE INC | NEW YORK, NY | 237112974 |
| $33,689,770 | st jude children's research hospit | ST JUDE CHILDRENS RESEARCH HOSPITA | MEMPHIS, TN | 620646012 |
| $32,000,000 | BLOOMBERG FAMILY FOUNDATION INC TH | JEROME AND SONDRA BLOOMBERG FAMILY | PLAINVIEW, NY | 113350909 |
| $31,352,878 | Jewish Federations of North Americ | THE JEWISH FEDERATIONS OF NORTH AM | NEW YORK, NY | 131624240 |
| $30,381,486 | Jewish Education Project | JEWISH ENTERTAINMENT EDUCATION PRO | NEW YORK, NY | 921813771 |
| $29,929,710 | Johnson C Smith University | JOHNSON C SMITH UNIVERSITY INCORPO | CHARLOTTE, NC | 250983069 |
| $29,349,904 | Hospital for special surgery | HOSPITAL FOR SPECIAL SURGERY FUND  | NEW YORK, NY | 136714749 |
| $28,902,966 | TRUSTEES OF COLUMBIA UNIVERSITY IN | TRUSTEES OF COLUMBIA UNIVERSITY IN | NEW YORK, NY | 911859360 |
| $28,287,513 | Blue Meridian | BLUE MERIDIAN PARTNERS INC | NEW YORK, NY | 815086187 |
| $27,435,031 | Children's Museum of Manhattan | CHILDRENS MUSEUM OF MANHATTAN | NEW YORK, NY | 132761376 |

_113 rows total; top 40 shown._

## 3. REVIEW — token match but the state disagrees (your judgement)

| dollars | filed name | filed state | proposed org | proposed state | EIN |
|---:|---|---|---|---|---|
| $264,729,922 | Fidelity Charitable Gift Fund | OH | FIDELITY INVESTMENTS CHARITABLE  | MA | 110303001 |
| $104,120,500 | FIDELITY CHARITABLE GIFT FUND | NY | FIDELITY INVESTMENTS CHARITABLE  | MA | 110303001 |
| $103,414,295 | smithsonian institution | DC | MARGUERITE V SCHNEEBERGER TRUST  | NY | 276333290 |
| $83,386,249 | FIDELITY CHARITABLE GIFT FUND | KY | FIDELITY INVESTMENTS CHARITABLE  | MA | 110303001 |
| $50,094,381 | doctors without borders | NY | NATUROPATHIC DOCTORS WITHOUT BOR | AZ | 453083348 |
| $34,036,209 | Givewell | CA | THE GIVEWELL PROJECT | NJ | 393493440 |
| $25,396,966 | American Online Giving Foundatio | FL | AMERICAN ONLINE GIVING FOUNDATIO | DE | 810739440 |
| $20,452,187 | Fidelity Gift Fund | KY | FIDELITY INVESTMENTS CHARITABLE  | MA | 110303001 |
| $20,150,000 | ICAHN SCHOOL OF MEDICINE | PA | ICAHN SCHOOL OF MEDICINE AT MOUN | NY | 136171197 |
| $16,168,861 | GROWALD CLIMATE FUND | DC | GROWALD CLIMATE FUND INC | MA | 464209325 |
| $15,898,355 | SCHRODINGER INC | NY | SCHRODINGER ACADEMY | MI | 823803696 |
| $14,973,630 | AMERICAN ONLINE GIVING FOUNDATIO | OH | AMERICAN ONLINE GIVING FOUNDATIO | DE | 810739440 |
| $10,645,966 | Center for Popular Democracy Inc | NY | CENTER FOR POPULAR DEMOCRACY | DC | 453813436 |

## 4. REJECT — proposal fails validation, top 25 by dollars

Leave unresolved. The proposed EIN is a different organisation.

| dollars | filed name | bad proposal |
|---:|---|---|
| $390,733,346 | UCSF Foundation | UCSF DISCOVERY FELLOWS FUND |
| $358,000,000 | WK Kellogg Foundation | KELLOGGSVILLE WARM-A-HEART |
| $291,639,352 | DAF - STABLER CHARITABLE FUND | DONALD B AND DOROTHY L STABLER FOUNDATIO |
| $256,501,253 | Schwab Charitable Fund | THE GEORGE SCHWAB AND LEONA LAUDER FOUND |
| $245,030,807 | Columbia University | SUFFOLK COUNTY POLICE DEPT COLUMBIA ASSO |
| $168,067,266 | Schwab Charitable Fund | SCHWAB DRIVE BAPTIST CHURCH |
| $166,952,218 | University of pennsylvania | PENNSYLVANIA CITIZENS FOR BETTER LIBRARI |
| $165,927,566 | Fidelity Charitable | FIDELITY HEALTH CARE INC |
| $159,664,587 | Amalgamated Charitable Foundation In | AMALGAMATED TRANSIT UNION |
| $141,052,188 | DONOR ADVISED FUND | DONOR ADVISED FUNDS OF THE DIOCESE OF NO |
| $127,449,484 | Northwestern Memorial Foundation | NORTHWESTERN MEMORIAL HEALTHCARE |
| $122,093,879 | THE BROAD INSTITUTE | SCHOOL YEAR ABROAD INC |
| $121,385,071 | amalgamated charitable foundation | AMALGAMATED TRANSIT UNION |
| $119,485,000 | Charter Fund Inc DBA Charter School  | COMMONWEALTH CHARTER ACADEMY CHARTER SCH |
| $112,475,537 | Harvard University | HARVARD BLACK ALUMNI-ALUMNAE SOCIETY INC |
| $100,029,975 | LA County Museum of Art | ORANGE COUNTY SHERIFFS MUSEUM & EDUCATIO |
| $96,120,270 | University of Notre Dame | ASSOCIATION OF NOTRE DAME CLUBS INC |
| $90,000,000 | MS Gift | GIFTS OF THE SPIRIT CHURCH CORP |
| $88,710,293 | Schwab Charitable | SCHWAB DRIVE BAPTIST CHURCH |
| $88,179,560 | Children's Medical Center Foundation | CHILDRENS MEDICAL CENTER RESEARCH INSTIT |
| $83,920,398 | Planned Parenthood Federation of Ame | PLANNED PARENTHOOD FEDERATION OF |
| $82,846,639 | UNIVERSITY OF KANSAS ENDOWMENT ASSOC | KANSAS UNIVERSITY ENDOWMENT ASSOC |
| $72,969,288 | UJA-Federation of New York | FEDERATION OF HELLENIC SOCIETIES OF GREA |
| $67,244,194 | Rice University | BEATRICE WOODMAN CHARITABLE TRUST 5661-0 |
| $66,878,306 | PEF israel endowment funds inc | P E F ISRAEL ENDOWMENT FUNDS INC |

## 5. NO CANDIDATE — top 20 by dollars

No BMF match was proposed. Most are donor-advised-fund sponsors and large
named foundations that appear under a different legal entity.

| dollars | filed name |
|---:|---|
| $7,751,201,000 | Bill & Melinda Gates Foundation |
| $1,437,132,241 | NA - SECTION 4948B |
| $404,193,628 | SCHWAB CHARITABLE DONOR ADVISED FUND |
| $189,385,239 | BILL & MELINDA GATES MEDICAL RESEARCH INSTIT |
| $174,070,761 | JP Morgan Charitable Giving Fund |
| $155,644,945 | UCB FOUNDATION |
| $115,000,000 | High Q Foundation Inc Attn Ken Slutsky Tax E |
| $100,493,600 | Broad Institute of MIT and Harvard |
| $100,000,000 | CHDI Foundation Inc Attn Ken Slutsky Tax Exe |
| $89,329,180 | goldman sachs philanthropy fund |
| $67,737,599 | NATIONAL TRUST HISTORIC PRESERVATN IN THE UN |
| $67,328,403 | CROSSROADS YMCA |
| $56,520,286 | CONTRIBUTIONS (DETAIL STATEMENT) |
| $53,727,843 | Tunnels to Towers |
| $52,844,989 | RECIPIENT STATEMENT ATTACHED |
| $52,000,000 | Charter School Growth Fund |
| $50,015,114 | FIDELITY CHARITABLE GIVING FUND |
| $47,538,958 | MIT |
| $46,943,780 | NYU- Langone Medical Center |
| $42,937,093 | REGENTS OF THE UNIVERSITY OF CALIFORNIA SAN  |
