# EOG Band Measurement — Runbook

**Status:** Retained operational runbook. The original South Lancaster season is complete and is
the baseline; use this procedure for a fresh measurement franchise or a short experimental arm.
The EOG attribute retune remains open in
[`Player_Attribute_Recalibration_Backlog.md`](Player_Attribute_Recalibration_Backlog.md).

Capture `[EOG-BAND]` data in the universal full-engine world by running locally, in-process,
against `gob-staging`. There is no deploy, UI, or auth step. The driver calls the authoritative
routes directly, so the staging service's environment does not control the run.

- **Default target:** `6a67882a2b2eb443f8c7789f` ("South Lancaster") in `gob-staging`.
- **Override for a new disposable franchise:** set both `GOB_MEASUREMENT_FRANCHISE_ID` and
  `GOB_MEASUREMENT_TEAM`.
- **Original completed baseline:** `6a66449127f0298bd27584c5`, now at week 27. Do not reuse it.
- **Tools:** `scripts/eog_measurement_season.py`, `scripts/run_eog_measurement.sh`, and
  `scripts/eog_band_report.py`.
- **Mutation warning:** the driver advances the selected franchise through its season.

## Prerequisites

```bash
export MONGO_URI='mongodb+srv://.../gob-staging'
```

Confirm the selected disposable franchise is at week 1. The driver is resumable, but only a fresh
week-1 state produces a clean full-season dataset. Its guards reject a URI without `gob-staging`,
a missing franchise, or a user-team mismatch.

## Full-season baseline or rerun

### 1. Prove capture with week 1

```bash
scripts/run_eog_measurement.sh --stop-after-week 1
```

The user-game line should report `[trained]`. Training failure is non-fatal to the driver but means
the run is not a clean trained-season baseline.

### 2. Validate the gate

```bash
python scripts/eog_band_report.py "$(pwd)/eog_band_measurement.jsonl"
```

All of these must hold:

| Assertion | Pass condition |
|---|---|
| Capture completeness | Week 1 contains exactly 64 distinct games |
| Provenance | The last header's pool setting and Git SHA match this run |
| Dataset shape | The full-engine branch, saturation, drift, and histogram tables render |

If week 1 is not exactly 64 games, stop and investigate before using the dataset.

### 3. Run the remaining regular season

```bash
scripts/run_eog_measurement.sh
```

Re-invoking after an interruption resumes from the franchise's current week. A full season produces
64 games per week for weeks 1–26. Weeks 27–34 intentionally produce no bands because postseason
team-attribute updates are frozen.

### 4. Produce the final report

```bash
python scripts/eog_band_report.py "$(pwd)/eog_band_measurement.jsonl"
```

Accept the dataset only when every captured regular-season week contains 64 games and there is no
postseason-freeze leak. The full-engine tables are the retune inputs.

## Short reproducible experimental arms

For a short arm, restore a disposable franchise to the same starting state and run the driver with
the pool disabled and an explicit seed:

```bash
export FRANCHISE_CPU_SIM_USE_POOL=0
scripts/run_eog_measurement.sh --stop-after-week 5 --seed 12345
```

The seed makes the same code and restored starting state reproducible. It does **not** make two
implementations an exact paired comparison when one implementation changes the EOG draw count or
order; use the poison-test rule documented in
[`Sim_Perf_Capstone.md`](Sim_Perf_Capstone.md) for that case.

## Safety and cleanup

- The staging service environment is untouched; only the selected staging franchise and the local
  JSONL file change.
- Use a new output path or remove/archive the old JSONL before a logically separate run. The logger
  appends, and the parser reports all records in the file.
- To rerun cleanly, restore the disposable franchise to week 1 or provision another one and set the
  two target override variables.
- This is a measurement/completeness gate, not an exact-diff determinism test.
