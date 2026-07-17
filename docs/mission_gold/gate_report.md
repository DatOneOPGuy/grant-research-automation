# Mission classifier — validation gate

Gold items scored: 313 (missing predictions: 0)

Confidence floor: 70


## Christian precision gate

- Christian predictions: 85
- Christian precision: **1.000** (threshold 0.95)
- Material Christian leaks (unflagged non-Christian gold predicted Christian): **0**

## Planted-leak self-test

- injected 1 synthetic secular->catholic leak
- gate on planted data passed = False (must be False)
- **gate correctly consumes leaks: True**

## Per-tradition metrics (effective, post-floor)

| tradition | support | precision | recall | F1 |
|---|---|---|---|---|
| catholic | 45 | 1.00 | 0.89 | 0.94 |
| christian_unspecified | 29 | 0.68 | 0.72 | 0.70 |
| evangelical_protestant | 20 | 0.71 | 0.50 | 0.59 |
| jewish | 38 | 1.00 | 0.95 | 0.97 |
| muslim | 31 | 0.88 | 0.97 | 0.92 |
| other_religion | 1 | 0.00 | 0.00 | 0.00 |
| secular | 132 | 0.99 | 0.84 | 0.91 |
| unknown | 17 | 0.37 | 1.00 | 0.54 |

## VERDICT: PASS

real gate passed = True; planted-leak self-test valid = True
