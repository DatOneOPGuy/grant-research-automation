# Run 20260709_235401_iter1_three_fixes

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 1: saint-default-catholic, name-only classification, christian_science tightened
- **Timestamp:** 2026-07-09T23:54:01

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **77.7%** (300 records)
- Major-category mean recall: **75.1%** (need ≥90%)
- Weak major F1 (<85%): evangelical_protestant, catholic

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **15**
- Non-Christian over-guessed as Christian: **4**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| other_religion | 2 | 0.0% | 0.0% | 0.0% |
| catholic | 62 | 100.0% | 43.5% | 60.7% |
| evangelical_protestant | 51 | 68.3% | 80.4% | 73.9% |
| jewish | 37 | 94.1% | 86.5% | 90.1% |
| secular | 147 | 92.3% | 89.8% | 91.0% |
| muslim | 1 | 100.0% | 100.0% | 100.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → unknown]** Providence St Joseph Hosp Foundatio — _The name contains a saint's name but lacks any clear religious or secular context._
- **[catholic → evangelical_protestant]** ST PETER'S EVANGELICAL LUTHERAN CHURCH AND SCHOOL — _Evangelical Lutheran church and school name_
- **[catholic → evangelical_protestant]** ST VIATOR SCHOOL — _Saint-named institution without additional secular context_
- **[catholic → secular]** St Petersburg Theatre — _No religious signals in the name and no purpose context provided._
- **[catholic → unknown]** C G JUNG SOCIETY OF ST LOUIS — _The name does not contain any clear religious or organizational signals._
- **[catholic → unknown]** PASSIONISTS INTERNATIONAL — _No definitive religious signal in the name._
- **[catholic → unknown]** HUGS ST JOHNS COUNTY — _No religious signals in the name or purpose context._
- **[catholic → evangelical_protestant]** ST MARY TRINITY CHURCH — _Saint-named organization without additional context_
- **[catholic → evangelical_protestant]** ST JOHN MISSIONARY BAPTIST CHURCH WPB — _Missionary Baptist Church indicates an Evangelical/Protestant affiliation._
- **[catholic → orthodox_christian]** Fr Mikhail Thabet St George Chur — _Contains 'St George', which is a common saint name associated with Orthodox Christian churches._
- **[catholic → evangelical_protestant]** PROVIDENCE COLLEGE SCHOOL OF BUSINESS — _The name 'Providence College School of Business' does not contain any explicitly religious terms and could be secular, but the context of a college or school name often defaults to Protestant evangelical due to the historical prevalence of such institutions in the United States._
- **[catholic → evangelical_protestant]** ST BARNABAS PRESBYTERIAN — _Bare saint name followed by a Christian denomination in the organization's name._
- **[catholic → secular]** St John's University - McCarthy Center — _Named after a saint but no explicit religious mission or secular signal present._
- **[catholic → evangelical_protestant]** MISSION OF OUR LADY OF THE ANGELS — _Contains the word 'Mission' and a saint's name, which defaults to Catholic unless explicitly Protestant._
- **[catholic → unknown]** ST CLAIR COUNTY CHILD — _No religious signals in the name and no additional context provided._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 67 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
