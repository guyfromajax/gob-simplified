# Test cleanup — stale zone-credit expectation, maxfail comment, backlog item

No engine or balance change. Tree `f4c018924` before, this commit after.

## 1. `test_zone_credit_shell` — EXPECTED re-derived

Approved: the zone sink (`cd2a08c3e`) intentionally moved empty-zone defenders, so the pinned credit map was stale.

**Old → new:**

```diff
-EXPECTED = {"2-3-zone": ["SG", "C"], "3-2-zone": ["PG", "SF"], "1-3-1-zone": ["PG", "PF"]}
+EXPECTED = {"2-3-zone": ["SG", "C"], "3-2-zone": ["PG", "SF"], "1-3-1-zone": ["PG"]}
```

**One entry moved.** 2-3 and 3-2 are unchanged; the 1-3-1 credit went from `["PG", "PF"]` to `["PG"]` — the power forward no longer lands close enough to the ball handler to be credited with him once the sink places him.

Derived by running the test's own `_guards()` helper against the current geometry with `GOB_ZONE_SINK` at its shipped default, not copied from the failure message. Checked at the same time:

- **stable on re-derivation** — identical on a second pass
- **the three shells still differ** — 3 distinct tuples, which is the property the test exists to prove

A comment above `EXPECTED` now records that it was re-derived after `cd2a08c3e`, that **the credit map depends on sink placement** (the credited defender comes from `defender_to_offensive_player`, built by asking which offensive player is nearest each defender's assigned coordinate — so moving defenders moves the credit), and that a future sink/anchor/spot-list change can legitimately move these values again.

**Both directions verified:**

| | result |
|---|---|
| default (`GOB_ZONE_SINK` on) | **6 passed** |
| `GOB_ZONE_SINK=0` | **1 failed** — `test_each_zone_credits_with_its_own_shell`, as expected: the sink's kill switch restores the pre-sink placement, which produces the pre-sink credit map |

That second line is the point of the exercise — the test is now pinned to the shipped geometry, and the old expectation is exactly what the kill switch reproduces.

## 2. `pytest.ini` — comment only

```ini
# maxfail hides the true failure count — run with --maxfail=1000 for a full picture
# (130 known failures as of 2026-09-19, see reports/test-triage-2026-09-19.md)
addopts = --maxfail=2 --disable-warnings -v
```

`--maxfail=2` is unchanged. The count in the comment is the pre-cleanup 130, which matches the triage report it points at; it is 129 after this commit.

## 3. `bugs.md` — one backlog item

Added **"Test-suite hygiene — 129 pre-existing failures [CODE-CLEANUP] — post-Founders"**: the grouped causes, the pointer to `reports/test-triage-2026-09-19.md`, the note that `--maxfail=2` is why a real regression hid for a day, and an explicit *do not fix piecemeal — work the groups*. **None of the 129 were touched.**

## Suite after

| | before | after |
|---|---|---|
| failed | 130 | **129** |
| passed | 2692 | **2693** |
| skipped / xfailed | 7 / 1 | 7 / 1 |

Command: `pytest tests/ --ignore=tests/e2e --maxfail=1000 -p no:cacheprovider`.

Set diff against the pre-cleanup run: **one id moved from failing to passing** (`test_zone_credit_shell::test_each_zone_credits_with_its_own_shell`) and **nothing newly failing**.
