# Classifier Experiment Runs

Each row is one prompt-tuning iteration. Newest at the bottom.

| Run | Model | n | Overall | Major recall | Christian leak | Gate | Note |
|---|---|---:|---:|---:|---:|:---:|---|
| 20260709_232814_qwen2_5_7b_baseline | qwen2.5:7b | 100 | 64.0% | 72.7% | 0 | ❌ FAIL | BASELINE (original prompt, reconstructed from initial 100-row review dump) |
| 20260709_235401_iter1_three_fixes | qwen2.5:7b | 300 | 77.7% | 75.1% | 4 | ❌ FAIL | Iter 1: saint-default-catholic, name-only classification, christian_science tightened |
| 20260710_001217_iter2_safety_fixes | qwen2.5:7b | 300 | 81.0% | 74.0% | 3 | ❌ FAIL | Iter 2: anti-default rule, FBO=for-benefit-of, Catholic markers (Our Lady/Holy Cross), saint+denomination split |
| 20260710_003055_iter3_caps_saint | qwen2.5:7b | 300 | 81.0% | 77.1% | 0 | ❌ FAIL | Iter 3: ALL-CAPS ST=Saint recognition, ST=State/city disambiguation, Congregation Beth-El->jewish, Catholic orders vocab |
| 20260710_004803_iter4_decision_order | qwen2.5:7b | 300 | 71.0% | 68.7% | 0 | ❌ FAIL | Iter 4: restructured as ordered decision procedure; saint rule as explicit IF/THEN with org-type list; leak counter-rules kept verbatim |
| 20260710_011103_iter5_world_knowledge | qwen2.5:7b | 300 | 69.0% | 69.1% | 6 | ❌ FAIL | Iter 5: authorize world knowledge in ladder (lists illustrative not exhaustive); jewish vocab (Hillel/Kollel/JCC); secular=any org type; Catholic orders+universities |
| 20260710_012836_iter6_leak_revert | qwen2.5:7b | 300 | 78.3% | 79.3% | 1 | ❌ FAIL | Iter 6: reverted STEP 5 widening (leak source), added Kollel/Hillel guard, fixed institution+person=secular not unknown |
| 20260710_064249_final_1000_records | qwen2.5:7b | 1000 | 76.8% | 78.4% | 2 | ❌ FAIL | Records-captured 1000-row run on final iter6 prompt, for GT-error adjustment of official confirmation |
