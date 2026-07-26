#!/usr/bin/env bash
# EOG-band measurement season runner. Sets all env, then drives the target
# franchise (6a66449127f0298bd27584c5, South Lancaster) through the regular
# season in-process. Writes the dataset to an ABSOLUTE local path so it survives
# independent of Railway's ephemeral filesystem.
#
# Usage:
#   export MONGO_URI='mongodb+srv://.../gob-staging'   # staging URI
#   scripts/run_eog_measurement.sh --stop-after-week 1   # week-1 capture gate
#   scripts/run_eog_measurement.sh                       # rest of the season
#
# Resumable: the driver reads the franchise's current week each run.
set -euo pipefail

: "${MONGO_URI:?export MONGO_URI for gob-staging first (must contain 'gob-staging')}"

export PYTHONHASHSEED=0
export GOB_EOG_BAND_LOG=1
export GOB_EOG_BAND_LOG_FILE="${GOB_EOG_BAND_LOG_FILE:-$(cd "$(dirname "$0")/.." && pwd)/eog_band_measurement.jsonl}"
export FRANCHISE_ALL_GAMES_FULL_SIM=1     # REQUIRED: keeps regular-season games off the distant scorer
export FRANCHISE_ALL_TEAMS_AUTOTRAIN=1    # real CPU training (target-world trajectories)
export FRANCHISE_CPU_SIM_USE_POOL=1       # fast CPU slate (set 0 to fall back to threads)

echo "Band log  -> $GOB_EOG_BAND_LOG_FILE"
echo "Flags     -> ALL_GAMES_FULL_SIM=$FRANCHISE_ALL_GAMES_FULL_SIM ALL_TEAMS_AUTOTRAIN=$FRANCHISE_ALL_TEAMS_AUTOTRAIN USE_POOL=$FRANCHISE_CPU_SIM_USE_POOL"
python scripts/eog_measurement_season.py "$@"
