"""Validation gate: production mission classifier vs the frozen gold set.

Measures per-tradition precision/recall/F1 and — decisively — the Christian
leak rate. The gate CONSUMES the leak counts: they flip the verdict to FAIL.
To prove the gate is not decorative, it plants a synthetic leak and asserts
the gate fails on it; if the planted leak does NOT fail the gate, the gate
itself is broken and the run must stop.

Exit 0 only if (real gate PASS) AND (planted-leak test correctly FAILED).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

GOLD = Path("logs/gold_labels.json")
RESULTS_DIR = Path("scratch/mission/gate/results")
REPORT = Path("logs/mission_gate_report.md")
CONF_FLOOR = 70
CHRISTIAN = {"evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified"}
# Unambiguously non-Christian gold labels; a Christian prediction on an
# UNFLAGGED one of these is a material leak.
NON_CHRISTIAN_STRICT = {"jewish", "muslim", "other_religion", "secular",
                        "mormon_lds", "christian_science"}
PASS_PRECISION = 0.95


def load_predictions() -> dict[str, tuple[str, int]]:
    preds: dict[str, tuple[str, int]] = {}
    for path in sorted(RESULTS_DIR.glob("batch_*.json")):
        for row in json.loads(path.read_text()):
            try:
                conf = int(row.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0
            preds[row["id"]] = (row.get("tradition", "unknown"), conf)
    return preds


def effective(pred: str, conf: int) -> str:
    """Below the confidence floor, the classifier abstains (unknown)."""
    return pred if conf >= CONF_FLOOR else "unknown"


def gate(pairs: list[tuple[str, str, bool]]) -> dict:
    """pairs = (gold_label, effective_pred, gold_flagged). Returns verdict."""
    christ_pred = [p for p in pairs if p[1] in CHRISTIAN]
    christ_correct = [p for p in christ_pred if p[0] in CHRISTIAN]
    precision = len(christ_correct) / len(christ_pred) if christ_pred else 1.0
    leaks = [p for p in pairs
             if p[1] in CHRISTIAN and p[0] in NON_CHRISTIAN_STRICT and not p[2]]
    passed = precision >= PASS_PRECISION and len(leaks) == 0
    return {"precision": precision, "n_christian_pred": len(christ_pred),
            "leaks": leaks, "passed": passed}


def per_tradition(pairs: list[tuple[str, str, bool]]) -> list[str]:
    labels = sorted({p[0] for p in pairs} | {p[1] for p in pairs})
    tp: dict[str,int] = defaultdict(int)
    fp: dict[str,int] = defaultdict(int)
    fn: dict[str,int] = defaultdict(int)
    for gold, pred, _ in pairs:
        if gold == pred:
            tp[gold] += 1
        else:
            fp[pred] += 1
            fn[gold] += 1
    out = ["| tradition | support | precision | recall | F1 |",
           "|---|---|---|---|---|"]
    for lab in labels:
        support = sum(1 for p in pairs if p[0] == lab)
        prec = tp[lab] / (tp[lab] + fp[lab]) if (tp[lab] + fp[lab]) else 0.0
        rec = tp[lab] / (tp[lab] + fn[lab]) if (tp[lab] + fn[lab]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        out.append(f"| {lab} | {support} | {prec:.2f} | {rec:.2f} | {f1:.2f} |")
    return out


def main() -> None:
    gold = json.loads(GOLD.read_text())
    preds = load_predictions()
    pairs: list[tuple[str, str, bool]] = []
    missing = 0
    for eid, g in gold.items():
        if eid not in preds:
            missing += 1
            continue
        raw, conf = preds[eid]
        pairs.append((g["label"], effective(raw, conf), bool(g["flagged"])))

    verdict = gate(pairs)
    # Planted-leak test: inject one synthetic secular->catholic leak and
    # confirm the gate flips to FAIL. Proves the gate consumes leak counts.
    planted = pairs + [("secular", "catholic", False)]
    planted_verdict = gate(planted)
    gate_consumes_leaks = planted_verdict["passed"] is False

    lines = ["# Mission classifier — validation gate\n",
             f"Gold items scored: {len(pairs)} (missing predictions: {missing})\n",
             f"Confidence floor: {CONF_FLOOR}\n",
             "\n## Christian precision gate\n",
             f"- Christian predictions: {verdict['n_christian_pred']}",
             f"- Christian precision: **{verdict['precision']:.3f}** "
             f"(threshold {PASS_PRECISION})",
             f"- Material Christian leaks (unflagged non-Christian gold "
             f"predicted Christian): **{len(verdict['leaks'])}**"]
    for gl, pr, _ in verdict["leaks"][:40]:
        lines.append(f"    - LEAK: gold={gl} predicted={pr}")
    lines += ["\n## Planted-leak self-test\n",
              "- injected 1 synthetic secular->catholic leak",
              f"- gate on planted data passed = {planted_verdict['passed']} "
              f"(must be False)",
              f"- **gate correctly consumes leaks: {gate_consumes_leaks}**",
              "\n## Per-tradition metrics (effective, post-floor)\n"]
    lines += per_tradition(pairs)
    verdict_str = "PASS" if verdict["passed"] else "FAIL"
    lines += [f"\n## VERDICT: {verdict_str}\n",
              f"real gate passed = {verdict['passed']}; "
              f"planted-leak self-test valid = {gate_consumes_leaks}"]
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-24:]))

    if not gate_consumes_leaks:
        print("\n!!! GATE IS BROKEN — planted leak did not fail the gate. STOP.")
        sys.exit(3)
    sys.exit(0 if verdict["passed"] else 1)


if __name__ == "__main__":
    main()
