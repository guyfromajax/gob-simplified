# EOG Band Measurement — Runbook

Capture a full regular season of `[EOG-BAND]` data from the measurement franchise,
in the universal full-engine world, so the retune can set real thresholds. Runs **locally,
in-process, against staging DB** — no deploy, no UI, no auth. The driver forces
the authoritative routes directly, so the staging service's environment is
irrelevant to data cleanliness.

- **Target franchise:** `6a66449127f0298bd27584c5` ("South Lancaster"), db `gob-staging`. Hardcoded in the driver; guarded (refuses any other team / non-staging URI).
- **Scripts:** driver `scripts/eog_measurement_season.py`, wrapper `scripts/run_eog_measurement.sh`, parser `scripts/eog_band_report.py`.
- ⚠️ **Mutates the franchise** — advances it through the season into postseason. It's disposable; that's expected.

## Prereqs
```bash
export MONGO_URI='mongodb+srv://.../gob-staging'   # staging (must contain 'gob-staging')
# Confirm the franchise is at week 1 before starting (driver is resumable, but a
# fresh season is cleanest).
```

## Step 1 — Week-1 capture gate (proves capture before committing anything)
```bash
scripts/run_eog_measurement.sh --stop-after-week 1
```
Advances exactly week 1. Watch stdout: the user-game line should say `[trained]`
(not `training SKIPPED`).

## Step 2 — Verify week 1 (all must pass)
```bash
python scripts/eog_band_report.py "$(pwd)/eog_band_measurement.jsonl"
```
| Assertion | Where | Pass = |
|---|---|---|
| **Gate #1: capture works** | `## 0 Week coverage` → `week 1: N games` | **N == 64** |
| Provenance correct | `## Run provenance` header | pool setting and git SHA match the run |
| Data present | `FULL-ENGINE GAMES` section | branch/saturation/histogram tables render |

If gate #1 shows anything other than 64, **stop** — a game was dropped from
capture (investigate before trusting downstream data).

## Step 3 — Commit Phase 0 (only after Step 2 passes)
```bash
git add BackEnd/api/franchise_routes.py scripts/eog_band_report.py \
        scripts/eog_measurement_season.py scripts/run_eog_measurement.sh
git commit   # message: "EOG Phase 0: band instrumentation + measurement harness"
```
The driver and parser now assume the universal full-engine routing.

## Step 4 — Run the rest of the season (resumes at week 2)
```bash
scripts/run_eog_measurement.sh            # advances until week > 26
```
~1,660 full games (63 CPU + 1 user × 26 wks) via the pool. Re-invoking after any
interruption continues from the franchise's current week.

## Step 5 — Final dataset report
```bash
python scripts/eog_band_report.py "$(pwd)/eog_band_measurement.jsonl"
```
Pass/fail: every regular-season week shows 64 games and there is no
postseason-freeze leak. The three full-engine tables are the retune inputs.

## Notes / safety
- **Staging service env is untouched.**
- **Weeks 27-34** produce no bands by design (postseason team-attr freeze); the
  parser states this and only flags it as an error if a 27-34 row appears.
- **Rollback:** nothing about staging changes except this one disposable
  franchise's data. To rerun clean, restore the franchise to week 1 (or use a new
  disposable franchise and update `TARGET_FRANCHISE_ID`).
- **Not the exact-diff:** RNG-coupling was closed by the getstate() proof; this run
  is the measurement + gate #1, not a determinism test.
