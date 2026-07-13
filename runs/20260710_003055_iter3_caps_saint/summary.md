# Run 20260710_003055_iter3_caps_saint

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 3: ALL-CAPS ST=Saint recognition, ST=State/city disambiguation, Congregation Beth-El->jewish, Catholic orders vocab
- **Timestamp:** 2026-07-10T00:30:55

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **81.0%** (300 records)
- Major-category mean recall: **77.1%** (need ≥90%)
- Weak major F1 (<85%): catholic

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **7**
- Non-Christian over-guessed as Christian: **0**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| other_religion | 3 | 100.0% | 33.3% | 50.0% |
| catholic | 39 | 94.7% | 46.2% | 62.1% |
| secular | 138 | 94.3% | 84.1% | 88.9% |
| jewish | 40 | 100.0% | 87.5% | 93.3% |
| evangelical_protestant | 76 | 92.0% | 90.8% | 91.4% |
| muslim | 3 | 100.0% | 100.0% | 100.0% |
| orthodox_christian | 1 | 50.0% | 100.0% | 66.7% |

## Top disagreements (full list in disagreements.md)

- **[catholic → unknown]** ST SEBASTION SPORTS PROJECT — _No religious signals in the name or context._
- **[catholic → unknown]** ST ANDREWS SCHOOL-BECKERER FAMILY FUND — _No religious signals in the name and no additional context provided._
- **[catholic → evangelical_protestant]** ST STEPHENS EPSICOPAL CHURCH — _Bare saint name followed by an explicitly Protestant denomination_
- **[catholic → unknown]** ST FRANCIS SHELTER — _No religious signals in the name or context._
- **[catholic → secular]** ST MARTIN'S PANTRY — _No religious signals in the name and no additional context provided._
- **[catholic → secular]** BIG BROTHERS BIG SISTERS OF ORANGE COUNT — _Name contains a secular organization name without any religious affiliations._
- **[catholic → unknown]** ST GEORGE ENDOWMENT FUND — _No religious signals in the name or purpose context._
- **[catholic → unknown]** FOOD CONNECTION OF ST LEO'S — _No religious signals in the name or purpose context._
- **[catholic → evangelical_protestant]** FRANCISCAN MISSION OUTREACH — _Mission is a term often used in evangelical contexts and the Franciscan order is Catholic but the combination with 'Mission' leans towards an evangelical mission._
- **[catholic → evangelical_protestant]** DELPHOS ST JOHNS CROSS COUNTRY — _Contains 'St' and 'Cross', which are Protestant markers_
- **[catholic → unknown]** ST JOHN OF GOD COMMUNITY — _No religious signals in the name and no additional context provided._
- **[catholic → secular]** ST JOSEPH COUNTY PARKS AND RECREATION — _Saint-named organization with no religious words in the name and context._
- **[catholic → evangelical_protestant]** ST PAUL LUTHERAN SCHOOL - GRAFTON — _Saint-named organization with a Lutheran denomination_
- **[catholic → evangelical_protestant]** St Mary of the Hills — _Saint-named organization without a clear Protestant or Catholic denomination_
- **[catholic → secular]** FRIENDS OF ST LAWRENCE-WATTS YOUTH CENTER — _No religious signals in the name._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 57 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
