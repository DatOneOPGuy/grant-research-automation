# Corroboration run — high-dollar review list

_2026-08-13. 1,630 name-only Christian recipients that already had 990 mission
text were run through the frozen classifier (gate re-confirmed: Christian
precision 1.000, 0 leaks, planted-leak self-test correctly FAILS)._

## Read this before trusting the "contradicted" column

731 recipients came back non-Christian. **They are overwhelmingly NOT name-rule
errors.** The mission classifier is precision-1.000 on positive Christian
claims, but its `secular` output is an *absence of explicit faith language in
the mission field*, not evidence that the organisation is secular. Southern
Methodist University's mission text says "education through research and
teaching"; it does not mention Methodism. The classifier is behaving exactly as
designed, and the organisation is still Methodist.

**No contradiction was written to the ledger.** Asserting `secular` on SMU,
TCU, Episcopal Collegiate School or International Justice Mission would be a
false statement, not a correction. Only the 520 corroborations were loaded.

A second correction: the task assumed mission text (priority 50) outranks the
name rule, so contradictions would auto-correct. **It does not** -- `rule` is
70 and `llm` is 50, so the name rule wins. Even had they been written, no
verdict would have flipped.

## 1. Corroborated — the win (520 recipients, $0.864B)

These are no longer name-only. Two independent sources now agree.

| received | recipient | name rule said | mission text said | quoted evidence |
|---:|---|---|---|---|
| $173,590,921 | GEORGETOWN UNIVERSITY | catholic | catholic (90) | *states "THE NATION'S OLDEST CATHOLIC AND JESUIT UNIVERSITY"* |
| $76,188,271 | UNIVERSITY OF ST THOMAS | catholic | catholic (92) | *states "Inspired by Catholic intellectual tradition"* |
| $38,189,387 | INDIANA WESLEYAN UNIVERSITY | evangelical_protestant | christian_unspecified (85) | *states "IS A CHRIST-CENTERED ACADEMIC COMMUNITY"* |
| $27,721,215 | CREIGHTON UNIVERSITY | catholic | catholic (97) | *states "Jesuit, Catholic universities"* |
| $21,035,840 | MARQUETTE UNIVERSITY | catholic | catholic (97) | *states "As a Catholic, Jesuit university"* |
| $19,575,916 | ABILENE CHRISTIAN UNIVERSITY | christian_unspecified | christian_unspecified (85) | *states "EDUCATE STUDENTS FOR CHRISTIAN SERVICE AND LEADERSHIP" and "CHRIST-CENTERED COMMUNITY"* |
| $17,747,742 | UNIVERSITY OF ST THOMAS | catholic | catholic (92) | *states "COMMITTED TO THE CATHOLIC INTELLECTUAL TRADITION"* |
| $16,549,845 | CATHOLIC UNIVERSITY OF AMERICA | catholic | catholic (96) | *states "THE NATIONAL UNIVERSITY OF THE CATHOLIC CHURCH"* |
| $15,847,715 | CATHOLIC SCHOOLS CENTER OF EXCELLENCE | catholic | catholic (85) | *states "TO ASSIST CATHOLIC ELEMENTARY SCHOOLS ACHIEVE EXCELLENCE"* |
| $14,675,000 | DESERT CHRISTIAN SCHOOLS INC | evangelical_protestant | christian_unspecified (78) | *states "Preschool-12 Christian education"* |
| $13,198,501 | FORDHAM UNIVERSITY | catholic | catholic (85) | *states "IN THE JESUIT TRADITION"* |
| $11,915,024 | ASBURY THEOLOGICAL SEMINARY | evangelical_protestant | evangelical_protestant (92) | *states "to evangelize and to spread scriptural holiness throughout the world through the love of Jes* |
| $11,897,694 | LIVING WATER INTERNATIONAL | evangelical_protestant | christian_unspecified (88) | *states "the gospel of Jesus Christ"* |
| $10,409,515 | FAITH ACADEMY OF BELLVILLE | christian_unspecified | christian_unspecified (85) | *states "CHRISTIAN ACADEMIC EDUCATION"* |
| $9,008,569 | KNIGHTS OF COLUMBUS CHARITABLE FUND IN | catholic | catholic (90) | *states "PHILANTHROPIC ACTIVITIES OF CATHOLIC INDIVIDUALS AND ORGANIZATIONS"* |
| $8,880,387 | ST LOUIS UNIVERSITY | catholic | catholic (92) | *states "GUIDED BY THE SPIRITUAL AND INTELLECTUAL IDEALS OF THE SOCIETY OF JESUS"* |
| $8,779,359 | DALLAS THEOLOGICAL SEMINARY | evangelical_protestant | evangelical_protestant (82) | *states "equipping godly servant-leaders for the proclamation of His Word and the building up of the * |
| $8,132,460 | UNION RESCUE MISSION | evangelical_protestant | christian_unspecified (85) | *states "WE EMBRACE PEOPLE EXPERIENCING HOMELESSNESS WITH THE COMPASSION OF CHRIST"* |
| $7,551,990 | CATHOLIC SCHOOLS FOUNDATION INC | catholic | catholic (95) | *states it funds education "AT CATHOLIC SCHOOLS LOCATED THROUGHOUT THE ARCHDIOCESE OF BOSTON"* |
| $7,483,298 | WHEATON COLLEGE | evangelical_protestant | christian_unspecified (85) | *states "serves Jesus Christ and advances his Kingdom"* |
| $7,274,739 | TREVECCA NAZARENE UNIVERSITY | evangelical_protestant | christian_unspecified (80) | *states it "IS A PRIVATE, CO-EDUCATIONAL, CHRISTIAN LIBERAL ARTS UNIVERSITY"* |
| $7,011,235 | LOYOLA UNIVERSITY OF CHICAGO | catholic | catholic (96) | *states "ONE OF THE NATION'S LARGEST JESUIT, CATHOLIC UNIVERSITIES"* |
| $6,843,349 | ST AUGUSTINE PREPARATORY ACADEMY INC | catholic | evangelical_protestant (85) | *states "PROVIDING EXCEPTIONAL NON-DENOMINATIONAL CHRISTIAN BASED EDUCATION"* |
| $6,254,956 | LUBBOCK CHRISTIAN UNIVERSITY | christian_unspecified | christian_unspecified (84) | *states "IS A CHRIST-CENTERED, ACADEMIC COMMUNITY OF LEARNERS"* |
| $5,596,876 | BIOLA UNIVERSITY INC | evangelical_protestant | evangelical_protestant (70) | *states "A private Christian university offering biblically-centered education"* |
| $5,453,625 | THE SAINT CONSTANTINE SCHOOL | catholic | christian_unspecified (80) | *states "TO PROVIDE CLASSICAL, CHRISTIAN EDUCATION"* |
| $4,898,050 | HOPE INTERNATIONAL | evangelical_protestant | christian_unspecified (80) | *states "AS WE PROCLAIM AND LIVE THE GOSPEL"* |
| $4,810,251 | SANTIAM CHRISTIAN SCHOOLS | evangelical_protestant | christian_unspecified (82) | *states "TO PROVIDE CHRISTIAN-BASED EDUCATION TO STUDENTS"* |
| $4,769,135 | PRISON FELLOWSHIP MINISTRIES | evangelical_protestant | christian_unspecified (90) | *states its mission "IS TO ENCOUNTER JESUS WITH THOSE IMPACTED BY INCARCERATION"* |
| $4,685,712 | LUTHERAN WORLD RELIEF INC | evangelical_protestant | evangelical_protestant (70) | *states "WORKS WITH LUTHERANS & PARTNERS AROUND THE WORLD TO END POVERTY"* |

## 2. Contradicted — held for your review, NOT written (731 recipients, $0.815B)

Ranked by dollars. Judge each on whether the organisation is genuinely
Christian despite a mission statement that does not say so.

| received | recipient | name rule said | mission text said | quoted evidence |
|---:|---|---|---|---|
| $123,594,414 | SOUTHERN METHODIST UNIVERSITY | evangelical_protestant | secular (85) | *states "education through research and teaching by creating and imparting knowledge"* |
| $75,634,985 | NEW YORK-PRESBYTERIAN FUND INC | evangelical_protestant | secular (88) | *states "FOR CHARITABLE, EDUCATIONAL & SCIENTIFIC PURPOSES, PRIMARILY FOR BENEFIT OF HEALTH CARE RELA* |
| $39,702,089 | INTERNATIONAL JUSTICE MISSION | evangelical_protestant | secular (90) | *states "TO PROTECT PEOPLE IN POVERTY FROM VIOLENCE"* |
| $36,026,370 | ST JOHNS COLLEGE | catholic | secular (88) | *states "TO PROVIDE POST-SECONDARY EDUCATION"* |
| $25,191,194 | EPISCOPAL COLLEGIATE SCHOOL | evangelical_protestant | secular (72) | *states only "TO EDUCATE AND INSTRUCT"* |
| $24,427,101 | TEXAS CHRISTIAN UNIVERSITY | christian_unspecified | secular (85) | *states "AN INSTITUTION OF HIGHER EDUCATION WHICH INCLUDES NINE MAJOR ACADEMIC UNITS"* |
| $20,191,911 | FRANCISCAN HEALTH FOUNDATION INC | catholic | secular (70) | *states "RAISE, INVEST, AND EXPEND CONTRIBUTIONS FOR THE BENEFIT OF FRANCISCAN ALLIANCE, INC. HEALTH * |
| $15,543,801 | CHRISTIAN COMMUNITY FOUNDATION INC | evangelical_protestant | secular (72) | *states "PROVIDE EXCELLENCE IN PERSONALIZED CHARITABLE GIVING SERVICES AND EDUCATION RESOURCES"* |
| $10,595,544 | FAITH IN ACTION NETWORK | christian_unspecified | other_religion (70) | *states "MORE THAN 40 DIFFERENT RELIGIOUS DENOMINATIONS AND FAITH TRADITIONS ARE PART OF THE FIA NETW* |
| $9,690,583 | GOOD SHEPHERD SERVICES | evangelical_protestant | secular (88) | *states "EXPANDS OPPORTUNITY FOR 30,500 NYC CHILDREN, YOUTH, AND FAMILIES THROUGH 90 PROGRAMS"* |
| $8,605,965 | ST BERNARD PROJECT INC | catholic | secular (92) | *states "WE REBUILD HOMES, INCREASE RESILIENCE, AND IMPROVE POLICIES"* |
| $7,394,279 | ST LAWRENCE UNIVERSITY | catholic | secular (95) | *states "TO PROVIDE AN INSPIRING AND DEMANDING UNDERGRADUATE EDUCATION IN LIBERAL ARTS"* |
| $7,059,057 | THOMAS AQUINAS COLLEGE | catholic | secular (85) | *text is only "POST SECONDARY EDUCATION-EDUCATIONAL ACTIVITIES"* |
| $7,040,030 | THE METHODIST HOSPITAL | evangelical_protestant | secular (85) | *states "PROVIDE MEDICAL CARE"* |
| $6,915,960 | ST ROSE DOMINICAN HEALTH FOUNDATION | catholic | secular (84) | *states "TO OFFER QUALITY, COMPASSIONATE CARE"* |
| $6,240,009 | MEMORIAL ASSISTANCE MINISTRIES INC | evangelical_protestant | secular (85) | *states "transforms families and communities through training, education, and economic empowerment"* |
| $5,486,800 | DAYSTAR FOUNDATION AND LIBRARY INC | evangelical_protestant | christian_science (90) | *states "historical items related to Christian Science and the Bible"* |
| $4,998,326 | ILLINOIS WESLEYAN UNIVERSITY | evangelical_protestant | secular (92) | *states "THE IDEAL OF A LIBERAL ARTS EDUCATION"* |
| $4,853,000 | SAMARITAN INNS INC | evangelical_protestant | secular (90) | *states "TO PROVIDE STRUCTURED HOUSING AND RECOVERY SERVICES FOR HOMELESS"* |
| $4,476,172 | ST COLETTA OF WISCONSIN INC | catholic | secular (90) | *states "SUPPORT PERSONS WITH DEVELOPMENTAL & OTHER CHALLENGES TO ACHIEVE A HIGH QUALITY OF LIFE"* |
| $4,422,714 | HOPE OF THE VALLEY RESCUE MISSION | evangelical_protestant | secular (85) | *states "ASSIST THE NEEDS OF EVERY HUNGRY HOMELESS PERSON IN THE VALLEY" with no religious signal* |
| $4,376,505 | ALL FAITHS FOOD BANK INC | christian_unspecified | secular (90) | *states "PROVIDE HEALTHY SOLUTIONS TO END HUNGER"* |
| $4,132,572 | HEART MINISTRY CENTER INC | evangelical_protestant | secular (85) | *states "PROVIDE FOOD, HEALTHCARE, AND A WAY FORWARD TO PEOPLE SEVERELY AFFECTED BY POVERTY"* |
| $4,004,159 | HOUSTON CHRISTIAN UNIVERSITY | christian_unspecified | secular (85) | *states "TO PROVIDE INSTRUCTION FOR APPROXIMATELY 5,200 STUDENTS"* |
| $3,688,296 | THE NEW YORK AND PRESBYTERIAN HOSPITAL | evangelical_protestant | secular (92) | *states "TO BE A LEADER IN THE PROVISION OF WORLD CLASS PATIENT CARE, TEACHING, RESEARCH"* |
| $3,655,176 | FAITH IN PLACE | christian_unspecified | other_religion (85) | *states "MULTIFAITH" and "EMPOWER PEOPLE OF DIVERSE FAITH AND SPIRITUALITIES"* |
| $3,606,042 | PACIFIC LUTHERAN UNIVERSITY INC | evangelical_protestant | secular (88) | *states "INTEGRATES THE LIBERAL ARTS, PROFESSIONAL STUDIES & CIVIC ENGAGEMENT"* |
| $3,569,000 | KAIROS FELLOWSHIP INC | evangelical_protestant | secular (95) | *states "ADVOCATING FOR CORPORATE ACCOUNTABILITY" regarding "THE INTERNET, DEMOCRACY, AND ORGANIZING"* |
| $3,447,067 | EPISCOPAL RELIEF AND DEVELOPMENT | evangelical_protestant | secular (80) | *states "ADVANCE LASTING CHANGE IN CO- MMUNITIES IMPACTED BY INJUSTICE"* |
| $3,150,463 | PRESBYTERIAN COLLEGE | evangelical_protestant | secular (88) | *states "OFFER A RIGOROUS EDUCATION WITH A BUILTIN SUPPORT NETWORK"* |

### My read of the top of that list

Genuinely Christian, mission text simply silent on faith — the name rule is
right and the classifier is right to abstain:

- **SOUTHERN METHODIST UNIVERSITY** ($123.6M) — Methodist
- **INTERNATIONAL JUSTICE MISSION** ($39.7M) — explicitly Christian human-rights organisation
- **EPISCOPAL COLLEGIATE SCHOOL** ($25.2M) — Episcopal
- **TEXAS CHRISTIAN UNIVERSITY** ($24.4M) — Disciples of Christ
- **FRANCISCAN HEALTH FOUNDATION** ($20.2M) — Catholic

Plausibly genuine name-rule false positives worth your attention:

- **ST BERNARD PROJECT INC** ($8.6M) — disaster-relief rebuilder, "WE REBUILD HOMES"; the saint's name looks incidental
- **ST LAWRENCE UNIVERSITY** ($7.4M) — historically Universalist, secular today
- **GOOD SHEPHERD SERVICES** ($9.7M) — Catholic-founded, largely secular NYC social services now

## 3. Abstained — unchanged (379 recipients, $0.533B)

Mission text was a cross-reference or boilerplate. These stay name-only.

