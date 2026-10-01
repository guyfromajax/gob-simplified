# fcc-fresh-after-game.spec.js flake — root cause + fix — 2026-10-01

Branch `fix/fcc-fresh-after-game-flake` off `origin/develop`. `fcc-fresh-after-game.spec.js`
(the "pre-game warm-paint cache plus a failed first read" test, among others) failed in two
court-chrome full runs and passed 5/5 isolated — a load flake. **Test-only fix.** No product,
sim, finalize, cpu_week_pool, or sim_rng change.

## Root cause (a test bug, reproduced deterministically)

The failing assertion is `expect(locker).toBeVisible({ timeout: 45000 })` in the shared helper
`simGameToLockerRoom` — the game-completion popup's "Go To Locker Room" button never appears,
because the game stalls before completion.

The franchise **Sim Full Game** path plays a pre-game experience whose CTA label **changes over
time**: it is first `"Submit & Tip Off"` (the matchups phase) and then, if that is not pressed,
rolls over to the display-only `"Tip Off"` (tip-off-ready). The gate-off path skips straight to
the completion popup. The old helper only matched `/Submit & Tip Off|Submit Defense Matchups/`
with a **15s** wait:

```js
const tipOff = page.getByRole('button', { name: /Submit & Tip Off|Submit Defense Matchups/ });
try { await tipOff.waitFor({ state: 'visible', timeout: 15000 }); await tipOff.click(); }
catch (e) { /* matchups are skipped when the gate is off */ }
await expect(locker).toBeVisible({ timeout: 45000 });   // <-- flaked here
```

- **Fast / normal:** `"Submit & Tip Off"` appears within 15s → clicked → sim runs → completion
  popup → locker button → pass.
- **Under load (slow court.html / Phaser load):** `"Submit & Tip Off"` appears *after* the 15s
  wait (or the CTA has already rolled over to `"Tip Off"`, which the regex **never matches**).
  The `catch` wrongly assumes "matchups gate off" and clicks nothing. The CTA sits at `"Tip Off"`,
  which the test never presses, so the game stays at tip-off-ready, the sim never finishes, the
  completion popup never shows, and `locker.toBeVisible()` times out at 45s.

### Evidence (not just N/N)

I could not reproduce via CPU throttling (the return path is dominated by fixed `setTimeout`s,
not CPU) or workers=3/4 contention (8/8, 66/66). The faithful lever was **slow serving**: an
env-gated delay on the page/JS/asset responses (`FCC_E2E_NET_DELAY_MS`, inert by default).

| Condition | Before fix | After fix |
|---|---|---|
| `FCC_E2E_NET_DELAY_MS=500`, x3 | 3/3 pass | — |
| `FCC_E2E_NET_DELAY_MS=2500`, x3 | **2/2 fail** (`locker.toBeVisible` 45s timeout, line 209; page stuck at live Q1 with a `"Tip Off"` button) | **3/3 pass** |

A no-op instrumentation run confirmed the CTA sequence directly: `DIAG-BTNS` logged
`"Submit & Tip Off"` for ~10s then `"Tip Off"` for the rest — the label the old regex missed.

## The fix (test-only, at the source)

`simGameToLockerRoom` now clicks **whichever** advance CTA is up — `Submit & Tip Off`,
`Submit Defense Matchups`, **or** `Tip Off` — repeatedly until the completion popup appears
(90s budget), so it is robust to a slow reveal under load and to the CTA label rolling over:

```js
const advanceCta = page.getByRole('button', { name: /^(Submit & Tip Off|Submit Defense Matchups|Tip Off)$/ });
const locker = page.locator('a.completion-button.locker-room-button');
const deadline = Date.now() + 90000;
while ((await locker.count()) === 0 && Date.now() < deadline) {
  if (await advanceCta.count()) await advanceCta.first().click({ timeout: 2000 }).catch(() => {});
  await page.waitForTimeout(400);
}
await expect(locker).toBeVisible({ timeout: 45000 });
```

Also added (inert by default): `FCC_E2E_NET_DELAY_MS` in the route handler, so this heavy helper
can be stress-tested on demand.

## Proof

- **`--repeat-each=10`** (whole file, no delay): **40/40 passed** (9.4m) — all 4 tests × 10, so :259 is 10/10 and the shared-helper fix is safe for the other three.
- Under-load (`FCC_E2E_NET_DELAY_MS=2500`): **before fix 2/2 fail → after fix 3/3 pass**.

## Gates (`.venv/bin/python`)

(on the tree after merging `origin/develop`)

- **pytest** `--ignore=tests/e2e -q`: **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (244s). 2 XPASS backend/pre-existing; `known_failures.py` not edited.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (real code, no pipe; new-surface 0/0/0). Test-only change — no UI source touched.
- **`check_migration_gates.py`**: **passed** — Gate A 0/0; Gate B 134 lines/43 files.
- **Full Playwright** (workers=1, port 8000, foreground under `/tmp/gob-full-playwright.lock`): **819 passed, 7 skipped, 0 failed** (13.4m). `fcc-fresh-after-game` is now green — the previously-flaky `:259` no longer fails.

STATUS: COMPLETE. Root cause (test helper missed the display-only "Tip Off" CTA and was timing-fragile under slow court load) found, reproduced deterministically, and fixed test-only. `--repeat-each=10` → 40/40; under-load before/after 2/2 fail → 3/3 pass; full suite green.
