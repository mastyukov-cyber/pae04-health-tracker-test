#!/usr/bin/env bash
# PAE-04 single-night synthetic browser stability QA, 13 Nov 2026 MSK.
# GitHub-hosted Linux only. No production data or live deployments.
set -Eeuo pipefail
if [[ $# -ne 1 ]]; then echo 'BLOCKED missing phase';exit 2;fi
phase="$1"
case "$phase" in
  phase1) start="2026-11-12 22:00:00 UTC"; end="2026-11-13 01:45:00 UTC";;
  phase2) start="2026-11-13 01:45:00 UTC"; end="2026-11-13 05:45:00 UTC";;
  *) echo "BLOCKED invalid phase";exit 2;;
esac
start_ts="$(date -u -d "$start" +%s)"
end_ts="$(date -u -d "$end" +%s)"
now="$(date -u +%s)"
reportdir="qa/integration-v02-browser/reports/night-$phase"
mkdir -p "$reportdir"
printf 'PHASE=%s\nSTART_UTC=%s\nEND_UTC=%s\n' "$phase" "$start" "$end" | tee "$reportdir/window.txt"
if (( now < start_ts )); then
  printf 'WAITING_TO_WINDOW seconds=%s\n' "$((start_ts-now))"
  sleep "$((start_ts-now))"
fi
now="$(date -u +%s)"
if (( now >= end_ts )); then
  echo 'RESULT=BLOCKED job started after permitted window' | tee "$reportdir/summary.txt"
  exit 2
fi
passed=0
failed=0
rounds=0
interval_seconds=600
while (( $(date -u +%s) < end_ts )); do
  rounds=$((rounds+1))
  slot_ts="$(date -u +%s)"
  echo "ROUND=$rounds TIME_UTC=$(date -u -Iseconds)" | tee -a "$reportdir/summary.txt"
  for engine in chromium webkit; do
    engine_upper="$(echo "$engine" | tr '[:lower:]' '[:upper:]')"
    path="$reportdir/$phase-$engine-round-$rounds.log"
    if timeout 180s env PAE04_ENGINE="$engine" node qa/integration-v02-browser/browser-e2e.mjs >"$path" 2>&1 \
       && grep -q "^RESULT=PASS CHECKS=19 FAILURES=0 MODE=REAL_$engine_upper" "$path" \
       && grep -q "SOURCE_SHA=2f511cc1211e998f18c56724cff580461b759118604e98a85d8e9706dcbd403a" "$path"; then
      passed=$((passed+1))
      echo "PASS engine=$engine round=$rounds" | tee -a "$reportdir/summary.txt"
    else
      failed=$((failed+1))
      echo "FAIL engine=$engine round=$rounds" | tee -a "$reportdir/summary.txt"
      tail -n 15 "$path" | tee -a "$reportdir/summary.txt"
    fi
  done
  now="$(date -u +%s)"
  next=$((slot_ts + interval_seconds))
  if (( next > end_ts )); then next=$end_ts; fi
  if (( next > now )); then sleep "$((next-now))"; fi
done
echo "RESULT=$([[ $failed -eq 0 ]] && echo PASS || echo FAIL) PHASE=$phase ROUNDS=$rounds BROWSER_RUNS_PASS=$passed BROWSER_RUNS_FAIL=$failed SCENARIOS_PER_RUN=19 FINISHED_UTC=$(date -u -Iseconds)" | tee -a "$reportdir/summary.txt"
if (( failed > 0 )); then exit 1; fi
