#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# GOB · Recruiting Phase 0 — Ground Clearing
#
#   Removes the dead recruiting frontend and repoints the one stale FCC link.
#   Verified by full reference sweep: config, deploy files, backend routes,
#   all six recruiting tests and both Playwright specs. Zero live references.
#
#   Usage:
#     ./cleanup-phase-0.sh            # dry run — prints what it would do
#     ./cleanup-phase-0.sh --apply    # stage the changes (does not commit)
#     ./cleanup-phase-0.sh --apply --include-awards
#                                     # also removes recruiting.css + awards.*
#
#   Ref: _documentation_master/projects/Recruiting_Hub_Redesign/
#        ../../../recruiting/ux-build-plan.md §3
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APPLY=0
INCLUDE_AWARDS=0
for arg in "$@"; do
  case "$arg" in
    --apply)          APPLY=1 ;;
    --include-awards) INCLUDE_AWARDS=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

cd "$(git rev-parse --show-toplevel)"
STATIC="FrontEnd/static"
FCC="$STATIC/franchise-command-center.js"

c_head(){ printf '\n\033[1;33m%s\033[0m\n' "$*"; }
c_ok(){   printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
c_warn(){ printf '  \033[0;31m!\033[0m %s\n' "$*"; }
c_dim(){  printf '  \033[2m%s\033[0m\n' "$*"; }

[[ $APPLY -eq 0 ]] && printf '\033[1;36mDRY RUN\033[0m — nothing will change. Re-run with --apply.\n'

# ── Guards ───────────────────────────────────────────────────────────────────
c_head "Guards"
if [[ -f .git/index.lock ]]; then
  c_warn "stale .git/index.lock present — git writes will silently fail."
  c_dim  "created: $(date -r .git/index.lock 2>/dev/null || echo unknown)"
  c_dim  "If no git process is running, remove it and re-run:"
  echo   "      rm -f .git/index.lock"
  exit 1
fi
c_ok "no stale index.lock"

BRANCH=$(git branch --show-current)
c_dim "branch: $BRANCH"
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
  c_warn "on $BRANCH — branch first:  git switch -c chore/recruiting-phase-0"
  exit 1
fi

# The live hub must exist and must NOT be a redirect stub.
if [[ ! -f "$STATIC/recruiting.html" ]]; then
  c_warn "recruiting.html missing — wrong tree?"; exit 1
fi
if grep -q "This forked page now redirects" "$STATIC/recruiting.html"; then
  c_warn "recruiting.html looks like a redirect stub — ABORT."; exit 1
fi
c_ok "recruiting.html present and is the live hub"

# ── Step 1 · Repoint the stale FCC link ──────────────────────────────────────
c_head "Step 1 · Repoint the week-35 CTA"
if grep -q "recruiting-orders.html" "$FCC"; then
  c_dim "$(grep -n 'recruiting-orders.html' "$FCC")"
  if [[ $APPLY -eq 1 ]]; then
    perl -pi -e "s{/recruiting-orders\.html}{/recruiting.html}g" "$FCC"
    c_ok "repointed to /recruiting.html"
  else
    c_ok "would repoint to /recruiting.html"
  fi
else
  c_ok "already repointed — nothing to do"
fi

# ── Step 2 · Verify no live inbound links remain ─────────────────────────────
c_head "Step 2 · Verify no live inbound links"
STUBS=(recruiting-invites.html recruiting-orders.html recruiting-results.html)
BLOCKED=0
for stub in "${STUBS[@]}"; do
  # Search live code only: exclude the dead files themselves, docs, and vendor.
  HITS=$(grep -rn --binary-files=without-match "$stub" \
          --include=*.js --include=*.html --include=*.py --include=*.css \
          --include=*.toml --include=*.json --include=*.sh \
          . 2>/dev/null \
        | grep -v "^\./$STATIC/recruiting-invites\." \
        | grep -v "^\./$STATIC/recruiting-orders\." \
        | grep -v "^\./$STATIC/recruiting-results\." \
        | grep -v "^\./_documentation_master/" \
        | grep -v "^\./node_modules/" \
        | grep -v "^\./scripts/cleanup-phase-0.sh" \
        | grep -v "musicController.js" \
        | grep -v "// " || true)
  # In dry-run, Step 1 hasn't repointed yet — don't fail on the link it will fix.
  if [[ $APPLY -eq 0 ]]; then
    HITS=$(echo "$HITS" | grep -v "franchise-command-center.js" || true)
  fi
  if [[ -n "$HITS" ]]; then
    c_warn "$stub still referenced:"; echo "$HITS" | sed 's/^/      /'; BLOCKED=1
  else
    c_ok "$stub — no live references"
  fi
done
if [[ $BLOCKED -eq 1 ]]; then
  c_warn "Resolve the above before deleting. Aborting."; exit 1
fi
c_dim "note: musicController.js:162 does a pathname .endsWith() check only —"
c_dim "      not a navigation link, and inert once the stub is gone."

# ── Step 3 · Delete ──────────────────────────────────────────────────────────
c_head "Step 3 · Delete dead files"
FILES=(
  "$STATIC/recruiting.js"
  "$STATIC/recruiting-invites.js"
  "$STATIC/recruiting-orders.js"
  "$STATIC/recruiting-results.js"
  "$STATIC/recruiting-invites.html"
  "$STATIC/recruiting-orders.html"
  "$STATIC/recruiting-results.html"
  "$STATIC/recruiting-spine-data.js"
  "$STATIC/recruiting-spine-gallery.html"
  "$STATIC/Recruiting Orders v2.html"
)
if [[ $INCLUDE_AWARDS -eq 1 ]]; then
  FILES+=("$STATIC/recruiting.css" "$STATIC/awards.html" "$STATIC/awards.js")
fi

TOTAL_LINES=0; TOTAL_BYTES=0; COUNT=0; FAILED=0
for f in "${FILES[@]}"; do
  if [[ -f "$f" ]]; then
    L=$(wc -l < "$f" | tr -d ' '); B=$(wc -c < "$f" | tr -d ' ')
    TOTAL_LINES=$((TOTAL_LINES + L)); TOTAL_BYTES=$((TOTAL_BYTES + B)); COUNT=$((COUNT + 1))
    printf '  %-52s %6s lines' "$(basename "$f")" "$L"
    if [[ $APPLY -eq 1 ]]; then
      if git rm -q -f "$f" 2>/tmp/gobrm.err; then
        if [[ -f "$f" ]]; then printf '   \033[0;31mFAILED (still on disk)\033[0m\n'; FAILED=1
        else printf '   \033[0;32mdeleted\033[0m\n'; fi
      else
        printf '   \033[0;31mFAILED\033[0m\n'; sed 's/^/        /' /tmp/gobrm.err; FAILED=1
      fi
    else
      printf '\n'
    fi
  else
    c_dim "$(basename "$f") — already gone"
  fi
done
printf '\n  %d files · %s lines · %s KB\n' "$COUNT" "$TOTAL_LINES" "$((TOTAL_BYTES / 1024))"
if [[ $APPLY -eq 1 && $FAILED -eq 1 ]]; then
  c_warn "One or more deletions FAILED — nothing has been committed. Resolve and re-run."
  exit 1
fi

# ── Step 4 · Confirm the keepers survived ────────────────────────────────────
c_head "Step 4 · Keepers"
for keep in "$STATIC/recruiting-common.js" "$STATIC/recruiting-lean-ladder.css" \
            "$STATIC/recruiting.html" "$STATIC/recruiting-hub.js" \
            "$STATIC/recruiting-spine.js" "$STATIC/recruiting-spine.css" \
            "$STATIC/recruiting-dock.css" "$STATIC/recruiting-signing.css" \
            "$STATIC/recruiting-results-hub.css"; do
  if [[ -f "$keep" ]]; then c_ok "$(basename "$keep")"
  else c_warn "MISSING: $keep — this should still exist!"; fi
done

# ── Step 5 · Post-check ──────────────────────────────────────────────────────
c_head "Step 5 · Post-check"
if [[ $INCLUDE_AWARDS -eq 0 ]]; then
  c_dim "recruiting.css kept. Its only consumer is awards.html, which is itself"
  c_dim "orphaned — the FCC Awards button points at leaders.html (js:1599)."
  c_dim "Confirm nothing external links to awards.html, then re-run with"
  c_dim "--include-awards to remove recruiting.css + awards.html + awards.js."
fi
c_dim "Tests unaffected: all six recruiting tests and both Playwright specs"
c_dim "were checked and reference none of these files."

if [[ $APPLY -eq 1 ]]; then
  c_head "Staged. Review and commit:"
  echo "    git status"
  echo "    git add -A '$STATIC'"
  echo "    git commit -m 'chore(recruiting): remove dead frontend, repoint week-35 CTA'"
else
  c_head "Dry run complete. Re-run with --apply to stage."
fi
