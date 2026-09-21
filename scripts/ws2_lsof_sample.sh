#!/bin/bash
# Sample TCP sockets of the loopback server and its descendants.
# Logs any non-loopback remote to the outfile. Zero such lines is the gate.
set -euo pipefail
PARENT="${1:?parent pid}"
OUT="${2:-/tmp/ws2-season-lsof.log}"
INTERVAL="${3:-15}"
: >"$OUT"
echo "# lsof sample parent=$PARENT interval=${INTERVAL}s started $(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$OUT"

descendants() {
  local pid="$1"
  local kids child
  echo "$pid"
  kids="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $kids; do
    descendants "$child"
  done
}

while kill -0 "$PARENT" 2>/dev/null; do
  pids="$(descendants "$PARENT" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  plist="${pids// /,}"
  raw="$(lsof -nP -a -p "$plist" -iTCP 2>/dev/null || true)"
  remote="$(printf '%s\n' "$raw" | awk 'NR>1 && $9 !~ /127\.0\.0\.1/ && $9 ~ /->/ {print}')"
  n_remote="$(printf '%s\n' "$remote" | awk 'NF{c++} END{print c+0}')"
  echo "$stamp pids=$(echo $pids | wc -w | tr -d ' ') remote=$n_remote" >>"$OUT"
  if [ "$n_remote" -gt 0 ]; then
    printf '%s\n' "$remote" >>"$OUT"
  fi
  sleep "$INTERVAL"
done
echo "# parent exited $(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$OUT"
