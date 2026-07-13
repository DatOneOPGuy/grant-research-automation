# Run 20260710_011103_iter5_world_knowledge

- **Model:** qwen2.5:7b
- **Sample size:** 300
- **Note:** Iter 5: authorize world knowledge in ladder (lists illustrative not exhaustive); jewish vocab (Hillel/Kollel/JCC); secular=any org type; Catholic orders+universities
- **Timestamp:** 2026-07-10T01:11:03

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **69.0%** (300 records)
- Major-category mean recall: **69.1%** (need ≥90%)
- Weak major F1 (<85%): evangelical_protestant, catholic, jewish, secular

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **3**
- Catholic/Evangelical confusion: **4**
- Non-Christian over-guessed as Christian: **3**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| catholic | 53 | 100.0% | 64.2% | 78.2% |
| secular | 141 | 93.2% | 68.1% | 78.7% |
| evangelical_protestant | 70 | 87.7% | 71.4% | 78.7% |
| jewish | 33 | 100.0% | 72.7% | 84.2% |
| muslim | 1 | 100.0% | 100.0% | 100.0% |
| other_religion | 2 | 66.7% | 100.0% | 80.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → secular]** THE WOMEN'S FOUNDATION OF GREATER SAINT LOUIS — _The name does not contain any religious signals and is clearly a foundation._
- **[catholic → orthodox_christian]** ST MARY & ST STEPHEN COPTIC ORTHODOX CHURCH — _Contains 'St' before personal names and mentions Coptic Orthodox._
- **[catholic → unknown]** TOWN OF WEST ST MODESTE — _Bare reference to a town name without any religious or organizational signals._
- **[catholic → secular]** ACADEMY PREP CENTER OF ST PETERSBURG — _No religious words in the name._
- **[catholic → orthodox_christian]** ST GREGORY OF SINAI MONASTERY — _Contains the saint name 'St Gregory of Sinai'_
- **[catholic → unknown]** PERE MARQUETTE MEMORIAL ASSOCIATION — _Bare organization name with no clear religious or secular signal_
- **[catholic → evangelical_protestant]** WYOMING MISSION FOR UKRAINE RELIEF CO ST JOHN'S EPISCOPAL CHURCH — _contains 'Episcopal' and 'St John's', which are Protestant denominational markers_
- **[catholic → secular]** THE FRIENDS OF THE SAINT PAUL PUBLIC LIBRARY — _No religious signals present in the name._
- **[catholic → evangelical_protestant]** ST JOHN APOSTOLIC HOLINESS CHURCH — _Contains 'ST' before a saint name and no other Christian denomination signal._
- **[catholic → evangelical_protestant]** Episcopal Diocese of Western Louisiana - Episcopal — _The term 'Episcopal' is a denomination within Protestant Christianity, and without additional context, it cannot be definitively classified as Catholic or Jewish._
- **[catholic → unknown]** HISTORIC SAINT PAUL — _ambiguous name without clear religious or secular context_
- **[catholic → orthodox_christian]** ST NICHOLAS GREEK ORTHODOX CHURCH NATIONAL SHRINE — _Orthodox church with a saint name_
- **[catholic → unknown]** ST ANDREWS CHURCH — _Bare church name without specific denominational signal or other context_
- **[catholic → unknown]** UNIV OF ST THOMAS FBO TAE KOSMO — _Bare acronym and truncated fragment without clear purpose or context._
- **[catholic → unknown]** E11 St Block Association — _Bare acronym and truncated fragment without clear religious or secular context._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 93 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
