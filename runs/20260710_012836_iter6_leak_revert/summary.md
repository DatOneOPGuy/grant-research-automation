# Run 20260710_012836_iter6_leak_revert

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 6: reverted STEP 5 widening (leak source), added Kollel/Hillel guard, fixed institution+person=secular not unknown
- **Timestamp:** 2026-07-10T01:28:36

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **78.3%** (300 records)
- Major-category mean recall: **79.3%** (need ≥90%)
- Weak major F1 (<85%): catholic

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **4**
- Non-Christian over-guessed as Christian: **1**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| catholic | 51 | 100.0% | 66.7% | 80.0% |
| secular | 153 | 95.3% | 79.1% | 86.4% |
| evangelical_protestant | 68 | 91.5% | 79.4% | 85.0% |
| jewish | 25 | 100.0% | 92.0% | 95.8% |
| mormon_lds | 1 | 100.0% | 100.0% | 100.0% |
| muslim | 1 | 100.0% | 100.0% | 100.0% |
| other_religion | 1 | 25.0% | 100.0% | 40.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → secular]** ST LOUIS FIREFIGHTERS COMMUNITY OUTREACH — _No religious signals present in the name._
- **[catholic → evangelical_protestant]** ST LUKES EPISCOPAL — _Contains 'St' and no clear Catholic or other Christian denomination signal_
- **[catholic → unknown]** BIG BROTHERS BIG SISTERS OF TAMPA B — _No clear religious or secular signal in the name._
- **[catholic → evangelical_protestant]** CHAPEL OF THE HOLY CROSS LUTHERAN C — _Contains 'Holy Cross' and no Catholic signals_
- **[catholic → episcopal]** THE EPISCOPAL DIOCESE OF AR — _Episcopal diocese vocabulary_
- **[catholic → unknown]** GUADALUPE CENTER EDUCATIONAL — _Barely recognizable as potentially religious due to the name 'Guadalupe,' but no clear Christian or Catholic signals are present._
- **[catholic → secular]** ST LOUIS CHILDRENS HOSPITAL FDNTN — _Contains 'ST' which likely abbreviates 'Saint', but no other religious signals are present._
- **[catholic → secular]** UF HEALTH ST JOHNS FOUNDATION — _Contains 'UF HEALTH' which suggests it is related to a university or health system, and 'ST JOHNS' does not indicate a Christian denomination in this context._
- **[catholic → unknown]** MEHNAZ FATIMA EDUCATION AND WELFARE — _No clear religious or organizational signals in the provided name._
- **[catholic → unknown]** ST LOUIS QUEER SUPPORT & HEALING — _No clear religious or organizational signal present._
- **[catholic → evangelical_protestant]** HELPING HANDS FOR THE HUNGRY SOUP KITCHEN ST CYPRIAN CHURCH — _Contains 'St Cyprian Church', which is a saint name and lacks other clear Christian denomination signals._
- **[catholic → unknown]** ST STEPHENS WAY — _Bare street name without any clear religious or organizational signal._
- **[catholic → unknown]** ST AIDAN'S CHAPEL OF DARTMOUTH — _No clear religious or organizational context provided._
- **[catholic → evangelical_protestant]** St Benedicts Classical Academy — _No clear religious signal, but the name 'St' before a saint's name typically indicates Catholicism or other Christian traditions, and in absence of more context, evangelical_protestant is chosen as the default Christian label._
- **[catholic → unknown]** ST SIMON ISLAND ATHLETIC ASSOCIATION — _Bare organization name with no religious or specific secular signals._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 65 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
