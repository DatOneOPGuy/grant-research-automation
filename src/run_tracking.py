"""Per-run artifact tracking for classifier prompt-tuning experiments.

Each experiment run gets its own timestamped folder under ``runs/`` holding a
human-readable ``summary.md``, the exact prompt used, the full raw model output,
and a readable disagreement list. A single ``runs/INDEX.md`` gains one row per
run so progress across prompt iterations is visible at a glance.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RUNS_ROOT = Path("runs")
MAJOR_CATEGORIES = ("evangelical_protestant", "catholic", "jewish", "secular")


def new_run_dir(label: str, root: Path = RUNS_ROOT) -> tuple[Path, str]:
    """Create runs/<timestamp>_<label>/ and return (path, run_id)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = "".join(char if char.isalnum() else "_" for char in label).strip("_") or "run"
    run_id = f"{stamp}_{slug}"
    path = root / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path, run_id


def evaluate_gate(report: dict[str, dict[str, float]]) -> dict:
    """Reproduce the SAFE-TO-RUN gate: all major cats present, mean recall >=90%, no F1 <85%."""
    major = [report[cat] for cat in MAJOR_CATEGORIES if report[cat]["support"]]
    major_recall = sum(item["recall"] for item in major) / len(major) if major else 0.0
    weak_f1 = [cat for cat in MAJOR_CATEGORIES
               if report[cat]["support"] and report[cat]["f1"] < 0.85]
    passed = len(major) == len(MAJOR_CATEGORIES) and major_recall >= 0.90 and not weak_f1
    return {
        "passed": passed, "major_recall": major_recall, "weak_f1": weak_f1,
        "present": len(major), "required": len(MAJOR_CATEGORIES),
    }


def metrics_table(report: dict[str, dict[str, float]]) -> str:
    """Render supported traditions as a markdown table, worst recall first."""
    rows = ["| Tradition | n | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|"]
    supported = [(cat, val) for cat, val in report.items() if val["support"]]
    for cat, val in sorted(supported, key=lambda item: item[1]["recall"]):
        rows.append(f"| {cat} | {val['support']:.0f} | {val['precision']:.1%} "
                    f"| {val['recall']:.1%} | {val['f1']:.1%} |")
    return "\n".join(rows)


def disagreement_lines(records: list[dict]) -> list[str]:
    """One readable bullet per disagreement: [truth -> predicted] name — reason."""
    lines = []
    for entry in records:
        if not entry["agree"]:
            lines.append(f"- **[{entry['ground_truth']} → {entry['predicted']}]** "
                         f"{entry['name']} — _{entry['reason']}_")
    return lines


def write_run(path: Path, run_id: str, config: dict, agreement: float,
              report: dict, gate: dict, safety: dict, records: list[dict]) -> None:
    """Write all artifacts for one run into its folder."""
    (path / "system_prompt.txt").write_text(config["system_prompt"], encoding="utf-8")
    (path / "records.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (path / "metrics.json").write_text(json.dumps(
        {"config": {key: val for key, val in config.items() if key != "system_prompt"},
         "overall_agreement": agreement, "gate": gate, "safety": safety, "report": report},
        indent=2), encoding="utf-8")
    _write_disagreements(path, records)
    _write_summary(path, run_id, config, agreement, report, gate, safety, records)


def _write_disagreements(path: Path, records: list[dict]) -> None:
    lines = disagreement_lines(records)
    body = "\n".join(lines) if lines else "_No disagreements with ground truth._"
    (path / "disagreements.md").write_text(
        f"# Disagreements ({len(lines)})\n\n{body}\n", encoding="utf-8")


def _write_summary(path: Path, run_id: str, config: dict, agreement: float,
                   report: dict, gate: dict, safety: dict, records: list[dict]) -> None:
    verdict = "✅ SAFE TO RUN" if gate["passed"] else "❌ TUNE THE PROMPT FIRST"
    disagreements = disagreement_lines(records)
    top = "\n".join(disagreements[:15]) if disagreements else "_None._"
    text = f"""# Run {run_id}

- **Model:** {config['model']}
- **Sample size:** {config['sample_size']}
- **Note:** {config.get('note') or '—'}
- **Timestamp:** {config['timestamp']}

## Verdict: {verdict}

- Overall exact agreement: **{agreement:.1%}** ({len(records):,} records)
- Major-category mean recall: **{gate['major_recall']:.1%}** (need ≥90%)
- Weak major F1 (<85%): {', '.join(gate['weak_f1']) or 'none'}

## Safety checks (must stay at 0)

- Jewish misclassified as Christian: **{safety['jewish_as_christian']}**
- Catholic/Evangelical confusion: **{safety['catholic_evangelical']}**
- Non-Christian over-guessed as Christian: **{safety['nonchristian_as_christian']}**

## Per-tradition metrics

{metrics_table(report)}

## Top disagreements (full list in disagreements.md)

{top}

## Files

- `records.json` — every record with the raw JSON the model emitted
- `disagreements.md` — all {len(disagreements)} disagreements with reasons
- `metrics.json` — machine-readable metrics + gate
- `system_prompt.txt` — the exact prompt used for this run
"""
    (path / "summary.md").write_text(text, encoding="utf-8")


def append_index(run_id: str, config: dict, agreement: float, gate: dict,
                 safety: dict, root: Path = RUNS_ROOT) -> None:
    """Append one row to runs/INDEX.md so cross-run progress is visible."""
    index = root / "INDEX.md"
    if not index.exists():
        index.write_text(
            "# Classifier Experiment Runs\n\n"
            "Each row is one prompt-tuning iteration. Newest at the bottom.\n\n"
            "| Run | Model | n | Overall | Major recall | Christian leak | Gate | Note |\n"
            "|---|---|---:|---:|---:|---:|:---:|---|\n", encoding="utf-8")
    leak = safety["jewish_as_christian"] + safety["nonchristian_as_christian"]
    gate_str = "✅ PASS" if gate["passed"] else "❌ FAIL"
    row = (f"| {run_id} | {config['model']} | {config['sample_size']} | {agreement:.1%} "
           f"| {gate['major_recall']:.1%} | {leak} | {gate_str} | {config.get('note') or '—'} |\n")
    with index.open("a", encoding="utf-8") as handle:
        handle.write(row)
