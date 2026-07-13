# Run 20260710_064249_final_1000_records

- **Model:** qwen2.5:7b
- **Sample size:** 1000
- **Note:** Records-captured 1000-row run on final iter6 prompt, for GT-error adjustment of official confirmation
- **Timestamp:** 2026-07-10T06:42:49

## Verdict: ❌ TUNE THE PROMPT FIRST

- Overall exact agreement: **76.8%** (1,000 records)
- Major-category mean recall: **78.4%** (need ≥90%)
- Weak major F1 (<85%): evangelical_protestant, catholic, secular

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **0**
- Catholic/Evangelical confusion: **15**
- Non-Christian over-guessed as Christian: **2**

## Per-tradition metrics

| Tradition | n | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| other_religion | 5 | 20.0% | 60.0% | 30.0% |
| muslim | 6 | 100.0% | 66.7% | 80.0% |
| catholic | 177 | 96.9% | 69.5% | 80.9% |
| evangelical_protestant | 206 | 92.9% | 76.7% | 84.0% |
| secular | 506 | 94.2% | 76.9% | 84.7% |
| jewish | 95 | 97.7% | 90.5% | 94.0% |
| mormon_lds | 2 | 100.0% | 100.0% | 100.0% |
| orthodox_christian | 3 | 33.3% | 100.0% | 50.0% |

## Top disagreements (full list in disagreements.md)

- **[catholic → evangelical_protestant]** ST STEPHEN'S UNITED METHODIST — _Contains 'ST' as a saint name and no other clear Christian denomination._
- **[catholic → orthodox_christian]** PHILOPTOCHOS SOCIETY (FIEND OF OF THE POOR) OF ST NECTARIOS — _Contains the term 'St Nektarios', an Orthodox saint name._
- **[catholic → evangelical_protestant]** ST MARK EVANGELICAL LUTHERAN — _Contains 'Evangelical Lutheran' and no conflicting signals_
- **[catholic → secular]** BIG BROTHERS BIG SISTERS OF NEW HA — _No religious signals present in the name._
- **[catholic → orthodox_christian]** CARMILITE MONASTERY — _Contains the term 'Carmelite', which refers to a religious order._
- **[catholic → unknown]** COLIN CHANDLERFT HAYS ST UNIV — _Bare person's name without any clear organizational context or religious signals._
- **[catholic → secular]** ST BARNABAS HEALTH CARE SYS FDN — _The name contains 'St' as an abbreviation for 'Saint', which follows the default rule of being Catholic unless a Protestant denomination word is present. However, since no such words are present and there is no other religious signal, it is classified as secular._
- **[catholic → evangelical_protestant]** ST PETERS UNITED METHODIST — _Contains 'ST' before a saint name and no other religious denomination signal_
- **[catholic → evangelical_protestant]** ST JOHN'S EPISCOPAL CHURCH OF HARBOR SPRINGS — _Contains the name 'St John' and no clear Catholic or Jewish signals._
- **[catholic → evangelical_protestant]** ST STEPHEN S EPISCOPLA CHURCH — _Contains 'St', which indicates a saint name, and no other Christian denomination is present._
- **[catholic → secular]** UNITED WAY OF GREATER ST LOUIS IN — _No religious signals in the name._
- **[catholic → unknown]** St Peter's 6th A — _No clear religious or organizational context provided._
- **[catholic → secular]** PENN ST UNIV FBO KAYLA PROBERT — _FBO (for the benefit of) indicates a secular context._
- **[catholic → unknown]** GONZAGA UNIVERSITY DMK SCHOLARSHIP — _Bare scholarship name without sufficient context or location to determine religious affiliation._
- **[catholic → other_religion]** MONASTERY OF THE HOLY SPIRIT — _Monastery suggests a religious institution that is not specifically Christian._

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all 232 disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
