"""Read-only measurement of name-rule dependency and accuracy.

Answers two questions with numbers rather than anecdote:

  1. Dependency -- how much of the product rests on a name rule with nothing
     else behind it.
  2. Accuracy -- wherever a name rule co-occurs with evidence we trust more,
     how often does the name rule agree?

Grades the name rule against the higher tiers (human, ntee, church_code_name,
group_exemption, llm/mission, grant_purpose), never against opinion. Writes
JSON checkpoints to logs/name_audit/ so the run resumes after an interruption.

Reads data/grants_v2.db and data/explorer_v5.db. Writes nothing but
checkpoints and the report.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

PIPELINE = Path("data/grants_v2.db")
EXPLORER = Path("data/explorer_v5.db")
CKPT = Path("logs/name_audit")
CHRISTIAN = {"evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified"}
# Tiers we grade the name rule AGAINST -- everything the ledger ranks above
# `rule`, plus the two below it that are independently sourced rather than
# name-derived (mission text and the funder's own grant purpose).
INDEPENDENT = {"human", "ntee", "church_code_name", "group_exemption",
               "llm", "grant_purpose"}
RULE_VERSION = re.compile(r"-v(\d+)$")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def save(name: str, payload) -> None:
    CKPT.mkdir(parents=True, exist_ok=True)
    (CKPT / f"{name}.json").write_text(json.dumps(payload, default=str))


def load(name: str):
    path = CKPT / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def newest_rule(rows: list[tuple[str, str]]) -> str | None:
    """Winning rule label: newest source_rule_id, honouring the v2->v4 chain.

    A retraction writes `unknown`, which means the rule declines to classify.
    """
    if not rows:
        return None
    best_version, best_label = -1, None
    for label, rule_id in rows:
        match = RULE_VERSION.search(rule_id or "")
        version = int(match.group(1)) if match else 0
        if version > best_version:
            best_version, best_label = version, label
    return None if best_label == "unknown" else best_label


def build_entity_map() -> dict:
    """entity_id -> {rule_label, independent: {method: label}}."""
    cached = load("entity_map")
    if cached:
        log(f"  entity map from checkpoint: {len(cached):,}")
        return cached
    conn = sqlite3.connect(f"file:{PIPELINE.resolve()}?mode=ro", uri=True)
    rule_rows = collections.defaultdict(list)
    independent = collections.defaultdict(dict)
    seen = 0
    for entity_id, method, label, rule_id, confidence in conn.execute(
            "SELECT entity_id, evidence_method, classification, "
            "source_rule_id, confidence FROM classification_evidence"):
        seen += 1
        if seen % 200_000 == 0:
            log(f"  read {seen:,} evidence rows")
        if method == "rule":
            rule_rows[entity_id].append((label, rule_id))
        elif method in INDEPENDENT and label != "unknown":
            # Keep the strongest confidence seen for a method.
            prior = independent[entity_id].get(method)
            if prior is None or confidence >= prior[1]:
                independent[entity_id][method] = (label, confidence)
    conn.close()
    entities = {}
    for entity_id in set(rule_rows) | set(independent):
        entities[entity_id] = {
            "rule": newest_rule(rule_rows.get(entity_id, [])),
            "independent": {m: v[0] for m, v
                            in independent.get(entity_id, {}).items()},
        }
    log(f"  entities with any evidence: {len(entities):,}")
    save("entity_map", entities)
    return entities


def load_facts() -> dict:
    """entity_id -> (dollars, resolved_tradition, resolved_method, name,
    identity_status, has_ein, has_website, has_mission)."""
    cached = load("facts")
    if cached:
        return cached
    conn = sqlite3.connect(f"file:{EXPLORER.resolve()}?mode=ro", uri=True)
    facts = {}
    for row in conn.execute("""
            SELECT entity_id, total_received, tradition, method, name,
                   identity_status,
                   (ein IS NOT NULL AND ein != '') AS has_ein,
                   (website IS NOT NULL AND website != '') AS has_website,
                   (mission_text IS NOT NULL AND mission_text != '')
                       AS has_mission
            FROM recipients"""):
        facts[row[0]] = list(row[1:])
    conn.close()
    log(f"  recipient facts: {len(facts):,}")
    save("facts", facts)
    return facts


def is_christian(label: str | None) -> bool:
    return label in CHRISTIAN


def agreement(rule_label: str, ind_labels: list[str]) -> str:
    """How the name rule compares with the trusted evidence."""
    rule_c = is_christian(rule_label)
    ind_c = [is_christian(x) for x in ind_labels]
    if rule_label in ind_labels:
        return "exact"
    if rule_c and all(ind_c):
        return "christian_agree_subtype_differs"
    if rule_c and not any(ind_c):
        return "FALSE_POSITIVE"
    if not rule_c and any(ind_c):
        return "FALSE_NEGATIVE"
    return "nonchristian_agree_subtype_differs"


def part1_dependency(entities: dict, facts: dict) -> dict:
    buckets = collections.defaultdict(
        lambda: {"n": 0, "dollars": 0, "by_tradition": collections.Counter()})
    for entity_id, ev in entities.items():
        fact = facts.get(entity_id)
        if not fact:
            continue
        dollars, resolved, _method = fact[0] or 0, fact[1], fact[2]
        if resolved is None:
            continue                      # unclassified: not in scope here
        rule_label, ind = ev["rule"], ev["independent"]
        if not rule_label and ind:
            key = "a_no_rule_involved"
        elif rule_label and ind:
            same = [m for m, v in ind.items()
                    if is_christian(v) == is_christian(rule_label)]
            key = ("b_rule_corroborated" if same
                   else "d_rule_contradicted_by_higher_tier")
        elif rule_label and not ind:
            key = "c_rule_is_SOLE_evidence"
        else:
            continue
        bucket = buckets[key]
        bucket["n"] += 1
        bucket["dollars"] += dollars
        bucket["by_tradition"][resolved] += 1
    return {k: {"n": v["n"], "dollars": v["dollars"],
                "by_tradition": dict(v["by_tradition"])}
            for k, v in buckets.items()}


def part2_accuracy(entities: dict, facts: dict) -> dict:
    per_tradition = collections.defaultdict(
        lambda: collections.Counter())
    per_tradition_dollars = collections.defaultdict(
        lambda: collections.Counter())
    errors = []
    checkable = 0
    for entity_id, ev in entities.items():
        rule_label, ind = ev["rule"], ev["independent"]
        if not rule_label or not ind:
            continue
        fact = facts.get(entity_id)
        dollars = (fact[0] or 0) if fact else 0
        checkable += 1
        verdict = agreement(rule_label, list(ind.values()))
        per_tradition[rule_label][verdict] += 1
        per_tradition_dollars[rule_label][verdict] += dollars
        if verdict in ("FALSE_POSITIVE", "FALSE_NEGATIVE"):
            errors.append({
                "entity_id": entity_id,
                "name": fact[3] if fact else None,
                "rule_said": rule_label,
                "trusted_said": ind,
                "dollars": dollars,
                "direction": verdict,
            })
    errors.sort(key=lambda e: -e["dollars"])
    return {
        "checkable": checkable,
        "per_tradition": {k: dict(v) for k, v in per_tradition.items()},
        "per_tradition_dollars": {k: dict(v) for k, v
                                  in per_tradition_dollars.items()},
        "top_errors": errors[:300],
        "error_totals": {
            "false_positive_n": sum(1 for e in errors
                                    if e["direction"] == "FALSE_POSITIVE"),
            "false_positive_dollars": sum(
                e["dollars"] for e in errors
                if e["direction"] == "FALSE_POSITIVE"),
            "false_negative_n": sum(1 for e in errors
                                    if e["direction"] == "FALSE_NEGATIVE"),
            "false_negative_dollars": sum(
                e["dollars"] for e in errors
                if e["direction"] == "FALSE_NEGATIVE"),
        },
    }


def part3_blindspot(entities: dict, facts: dict) -> dict:
    routes = collections.defaultdict(lambda: {"n": 0, "dollars": 0})
    at_risk = []
    for entity_id, ev in entities.items():
        if not ev["rule"] or ev["independent"]:
            continue                       # not name-only
        fact = facts.get(entity_id)
        if not fact:
            continue
        dollars, resolved, _m, name, identity, has_ein, has_web, has_mission \
            = (fact + [None] * 8)[:8]
        if resolved is None:
            continue
        dollars = dollars or 0
        key = ("christian" if is_christian(resolved) else "other")
        routes[f"{key}_total"]["n"] += 1
        routes[f"{key}_total"]["dollars"] += dollars
        if key != "christian":
            continue
        if has_mission:
            route = "already_has_mission_text_unused"
        elif has_ein and identity == "matched_bmf":
            route = "990_mission_pull (resolved EIN)"
        elif has_web:
            route = "website_statement_of_faith"
        elif identity in ("unresolved", "collision"):
            route = "needs_identity_resolution_first"
        else:
            route = "no_route_identified"
        routes[route]["n"] += 1
        routes[route]["dollars"] += dollars
        at_risk.append({"entity_id": entity_id, "name": name,
                        "dollars": dollars, "route": route,
                        "identity": identity, "tradition": resolved})
    at_risk.sort(key=lambda r: -r["dollars"])
    return {"routes": {k: v for k, v in routes.items()},
            "top_at_risk": at_risk[:200]}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.name_rule_audit",
                                 description=__doc__)
    ap.add_argument("--part", default="all")
    ap.parse_args()

    started = time.monotonic()
    log("building entity evidence map…")
    entities = build_entity_map()
    log("loading recipient facts…")
    facts = load_facts()

    for name, fn in (("part1", part1_dependency), ("part2", part2_accuracy),
                     ("part3", part3_blindspot)):
        if load(name):
            log(f"{name}: from checkpoint")
            continue
        log(f"{name}: computing…")
        save(name, fn(entities, facts))
        log(f"{name}: saved")
    log(f"done in {time.monotonic() - started:,.0f}s -> {CKPT}")


if __name__ == "__main__":
    main()
