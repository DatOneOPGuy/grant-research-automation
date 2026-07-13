# Run 20260710_001217_iter2_safety_fixes

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 2: anti-default rule, FBO=for-benefit-of, Catholic markers (Our Lady/Holy Cross), saint+denomination split
- **Timestamp:** 2026-07-10T00:12:17

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **81.0%** (300 records)
- Major-category mean recall: **74.0%** (need ≥90%)
- Weak major F1 (<85%): catholic

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **1**
- Catholic/Evangelical confusion: **8**
- Non-Christian over-guessed as Christian: **2**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| catholic | 54 | 100.0% | 38.9% | 56.0% |
| jewish | 28 | 100.0% | 75.0% | 85.7% |
| evangelical_protestant | 67 | 85.5% | 88.1% | 86.8% |
| secular | 150 | 91.6% | 94.0% | 92.8% |
| muslim | 1 | 100.0% | 100.0% | 100.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → unknown]** ST JOESPH'S INDIAN SCHOOL — _No religious signals in the name or purpose context._
- **[catholic → evangelical_protestant]** ST PETER'S EPISCOPAL — _St. Peter's with no explicit Catholic or secular signals_
- **[catholic → unknown]** ST VITO'S CHURCH COVID RELIEF — _No religious signals in the name or context._
- **[catholic → unknown]** St Augustine Health Center — _No religious signals in the name and no additional context provided._
- **[catholic → evangelical_protestant]** SAINT MARGARET'S EPISCOPAL CHURCH — _The name includes 'Saint' and 'Episcopal', which defaults to evangelical_protestant as Episcopal refers to the Anglican tradition, a branch of Christianity._
- **[catholic → unknown]** Birthright of St Joseph's County — _No religious signals in the name or purpose context._
- **[catholic → secular]** St Mary's Food Bank Alliance Depository — _No religious signals in the name and purpose context is unavailable._
- **[catholic → unknown]** Elegant Sisters of Houston — _No religious signals in the name or context._
- **[catholic → orthodox_christian]** HELLENIC COLLAGE & HOLY CROSS SCH — _Contains 'Holy Cross', which defaults to Orthodox Christian._
- **[catholic → unknown]** ST CATHERINE LABOURE SCHOOL FOR THE SHIRLEY GLASSMAN SCHOLARSHIP FUND — _No religious signals in the name and no additional context provided._
- **[catholic → secular]** OREGON ST UNIV FBO COOPER JOHNSON — _The name contains 'FBO' which stands for 'for the benefit of', indicating it is related to a specific person (Cooper Johnson) rather than a religious organization. The name does not contain any religious signals and thus is classified as secular._
- **[catholic → unknown]** ST JOACHIM & ANNE SCHOOL — _Bare saint name without a clear religious organization or additional context._
- **[catholic → evangelical_protestant]** ST SIMON STOCK - ST JOSEPH CHURCH — _Saint names without a specified Protestant denomination default to evangelical_protestant._
- **[catholic → unknown]** ST STEPHENS WAY — _No religious or organizational signals in the name._
- **[catholic → evangelical_protestant]** SAINT VINCENT DEPAUL — _Default to evangelical_protestant due to lack of specific Catholic or other religious signals in the name._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 57 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
