#!/usr/bin/env bash
# Overnight orchestration: validate the local classifier on a 1000-row sample,
# and only if the harness reports "SAFE TO RUN", launch the full classification pass.
set -uo pipefail
cd "$(dirname "$0")"

VAL_LOG="logs/overnight_validate.log"
FULL_LOG="logs/overnight_full.log"
mkdir -p logs

echo "=== [$(date)] Validation starting (1000-row sample) ==="
python3 -m src.validate_classifier --sample-size 1000 2>&1 | tee "$VAL_LOG"
val_status=${PIPESTATUS[0]}
echo "=== [$(date)] Validation exited with status $val_status ==="

if [ "$val_status" -ne 0 ]; then
  echo "!!! Validation crashed (exit $val_status). NOT running the full pass. See $VAL_LOG"
  exit 1
fi

if grep -q "SAFE TO RUN" "$VAL_LOG"; then
  echo "=== [$(date)] Gate PASSED (SAFE TO RUN). Launching full classification pass ==="
  python3 -m src.local_recipient_classification 2>&1 | tee "$FULL_LOG"
  full_status=${PIPESTATUS[0]}
  echo "=== [$(date)] Full classification exited with status $full_status ==="
  exit "$full_status"
else
  echo "!!! Gate FAILED: report says TUNE THE PROMPT FIRST. NOT running the full pass. See $VAL_LOG"
  exit 2
fi
