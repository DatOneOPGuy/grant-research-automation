# Run 20260709_232814_qwen2_5_7b_baseline

- **Model:** qwen2.5:7b
- **Sample size:** 100
- **Note:** BASELINE (original prompt, reconstructed from initial 100-row review dump)
- **Timestamp:** 2026-07-09T23:28:14

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **64.0%** (100 records)
- Major-category mean recall: **72.7%** (need ≥90%)
- Weak major F1 (<85%): catholic, secular

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **0**
- Non-Christian over-guessed as Christian: **0**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| secular | 47 | 83.3% | 53.2% | 64.9% |
| catholic | 23 | 100.0% | 56.5% | 72.2% |
| muslim | 3 | 100.0% | 66.7% | 80.0% |
| evangelical_protestant | 16 | 100.0% | 81.2% | 89.7% |
| jewish | 11 | 100.0% | 100.0% | 100.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → secular]** SAINT GREGORY THE GREAT — _The name includes a saint but there is no information about a religious mission._
- **[catholic → unknown]** PHOEBE FORDHAM — _Insufficient information to classify_
- **[catholic → unknown]** ST GABRIEL'S FRATERNUS — _The name suggests a religious context with a saint's name but lacks sufficient information to determine the specific religious affiliation or if it is secular._
- **[catholic → unknown]** NORTH DAKOTA ST UNIV FBO MORGAN LEBLANC — _Insufficient information to determine religious affiliation or secular status._
- **[catholic → secular]** ST RAYMONDS HIGH SCHOOL FOR BOYS — _The name includes a saint's name but the context suggests it is an educational institution without a religious mission._
- **[catholic → secular]** ST JOSEPH HOSPITAL FUNDATION — _The name contains a saint's name but the context suggests it is a secular foundation without a religious mission._
- **[catholic → secular]** 501 ST JUDE — _The name includes 'ST JUDE' which refers to Jude in Christianity, but the context indicates there is no religious mission, aligning it with a secular organization._
- **[catholic → orthodox_christian]** ST GEORGE MALANKARA ORTHODOX CHURCH (INACTIVE) (INACTIVE) — _The name includes 'Orthodox Church', which is a clear indicator of the Orthodox Christian tradition._
- **[catholic → secular]** ST MARTIN DE PORRES SENIOR CENTER — _The name contains a saint's name but there is no information indicating a religious mission._
- **[catholic → unknown]** PROJECT GRAD ST VINCENT — _insufficient information to determine religious or secular nature_
- **[evangelical_protestant → christian_science]** CHRIST CHURCH-ITHAN — _The name 'CHRIST CHURCH' is reminiscent of the Christian Science Church, and without additional context, this is the most likely classification._
- **[evangelical_protestant → unknown]** ADORATION CONVENT OF CHRIST THE KING (PINK SISTERS) — _Insufficient information to determine the classification with high confidence._
- **[evangelical_protestant → unknown]** NEW YORK PRESBYTERIANWEIL CORNELL — _Insufficient information to determine religious affiliation; could be secular or religious but purpose context is unavailable._
- **[muslim → unknown]** AMERICAN ISLAMIC OUTREACH — _Insufficient information to determine the classification with high confidence._
- **[secular → unknown]** EDINBORO UNIVERSITY FBO MORGAN WISSNER — _Insufficient information to classify_

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 36 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
