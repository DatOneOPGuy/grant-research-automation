# Outstanding Work — what we don't have / haven't done yet

As of 2026-07-02, after the Phase 2 build and full-country rebuild.

## Blocked on a decision or resource

1. **LLM recipient classification — not run.** Needs `ANTHROPIC_API_KEY`.
   ~905k recipients are pending tags (the $5k-threshold subset — the ones
   that would actually be classified — to be recounted after the final
   pass; it will be well above the earlier ~150k estimate since the grant
   set grew from 963k to 4.4M+). Until this runs, faith scores are
   computed from rule/seed tags only (~7% of recipients) and
   **systematically understate** Christian alignment — expect many false
   "No Significant Pattern" labels. Also worth switching the classifier
   to the Batch API before running (50% cheaper, ~1h turnaround);
   current code is sequential `messages.create`.
2. **ProPublica gap-fill — paused by Drake** at ~600 / 17,016 EINs.
   Resume is free (disk cache). Open decision: do the 17k
   no-e-file foundations matter to the client? (Mix of filing-deadline
   lag, new foundations, delinquent orgs, rare true paper filers.)
3. **17,016 universe rows have no filing data** (`data_found = No`) —
   name/city/state/NTEE/ProPublica link only. Shrinks naturally as the
   IRS publishes more filings; see refresh item below.

## Built in the plan but not implemented

4. **Website-discovery fallback** (plan step 6): web search for
   high-faith-score foundations whose 990 lists no website. Not built.
5. **Batch API mode for the classifier** — see item 1.
6. **Automated refresh pipeline.** Everything so far is a one-off build.
   No scheduled job to: pull the monthly BMF (universe changes), pull new
   IRS index months (late filers arrive continuously), download/parse new
   filings, re-score, re-export. Without it the database goes stale
   immediately. A monthly cron is the natural shape.
7. **Phase 1 alignment/opportunity score at national scale.** The old
   scorer (grantee-match 35 / keyword 30 / international 25 / focus 10)
   still reads the client's matches.csv list (~10.8k names). The national
   export ranks by Faith Alignment Score only. If the client wants the
   opportunity score on all 140k rows, scorer.run() needs refactoring to
   iterate the universe instead of matches.csv.

## Quality / verification gaps

8. **Dual-parser verification not re-run at national scale.**
   verify_profile.py passed 60/60 on the Phase 1 corpus; should re-run
   (larger sample) against the 358k-filing corpus. verify_inviteonly.py
   likewise.
9. **Contact email coverage is inherently thin** (~5% of filings include
   one). No secondary email source exists in the pipeline.
10. **Faith-score design caveats** (by client spec, worth restating):
    consistency component is capped at the 2023–2025 window (max 3
    years); a 100%-churches funder maxes at 65 ("Regular") because the
    weight table allocates only 40+15+10 to components a church-only
    funder can hit.
11. **"2025" means submission year, not tax year.** Most filings on disk
    are tax years 2023–2024; TY2025 returns largely don't exist yet
    anywhere. The consistency component effectively sees 2–3 tax years.

## Housekeeping

12. **Nothing is committed to git.** All Phase 2 source (11 modules),
    config changes, and docs are uncommitted working-tree changes.
13. **Disk:** data/ now holds ~30 GB (raw XMLs + BMF + zips artifacts);
    Phase 1 legacy CSVs (inviteonly*.csv, results.csv, etc.) still sit in
    the repo root and are superseded by foundation_database.csv.
14. **In flight right now:** final pipeline pass (re-parse including the
    48k zip-recovered filings → KB → faith scores → export).
