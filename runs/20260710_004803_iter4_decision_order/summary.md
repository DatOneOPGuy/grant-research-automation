# Run 20260710_004803_iter4_decision_order

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 4: restructured as ordered decision procedure; saint rule as explicit IF/THEN with org-type list; leak counter-rules kept verbatim
- **Timestamp:** 2026-07-10T00:48:03

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **71.0%** (300 records)
- Major-category mean recall: **68.7%** (need ≥90%)
- Weak major F1 (<85%): evangelical_protestant, catholic, secular

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **3**
- Non-Christian over-guessed as Christian: **0**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| other_religion | 4 | 66.7% | 50.0% | 57.1% |
| catholic | 58 | 97.0% | 55.2% | 70.3% |
| evangelical_protestant | 61 | 95.3% | 67.2% | 78.8% |
| jewish | 27 | 100.0% | 74.1% | 85.1% |
| secular | 149 | 90.7% | 78.5% | 84.2% |
| christian_science | 1 | 50.0% | 100.0% | 66.7% |

## Top disagreements (full list in disagreements.md)

- **[catholic → unknown]** BOYS HOPE-GIRLS HOPE OF ST LOUIS — _No religious signals in the name._
- **[catholic → unknown]** ST CATHERINE BY THE SEA — _No clear religious or organizational signal in the name._
- **[catholic → unknown]** ST LOUIS UNIVERSITY - SCHOLARSHIP - — _No clear religious or secular signals in the name._
- **[catholic → secular]** KENNESAW ST UNIV FBO EMILY MATTHEWS — _FBO acronym without a religious context_
- **[catholic → unknown]** SAINT DAVID'S CREATION STEWARDSHIP FUND — _No clear religious or organizational signals in the name._
- **[catholic → unknown]** CAPUCHINS SOUP KITCHEN — _No religious signals in the name._
- **[catholic → secular]** BIG BROTHERS BIG SISTERS OF INDIAN RIVER — _No religious signals in the name._
- **[catholic → evangelical_protestant]** SOC OF ST JOHN THE EVANGELIST — _Contains 'St John' which is a common name for evangelical Protestant churches but no Catholic saint names are present._
- **[catholic → unknown]** DON BOSCO CRISTO REY HIGH SCHOOL MD — _No clear religious or organizational signals in the name._
- **[catholic → secular]** ST JUDE CHILCREN'S RESEARCH HOSPITAL — _Explicitly secular research hospital name_
- **[catholic → unknown]** MOUNT CARMEL FOUNDATION — _No clear religious or organizational signal in the name._
- **[catholic → secular]** NORTH CAROLINA ST UNIV FBO KERA — _FBO abbreviation without a religious context_
- **[catholic → orthodox_christian]** St Lukes Antichian Orthodox Church — _Contains 'Antichian Orthodox' which indicates an Orthodox Christian denomination._
- **[catholic → unknown]** XITLALI ESPINOSA CO GONZAGA — _No religious signals in the provided name._
- **[catholic → secular]** Duquesne University 2 — _No religious signals in the name._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 87 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
