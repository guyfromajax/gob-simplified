# Dead UI cleanup — 2026-10-01

Branch `chore/dead-ui-cleanup` off `origin/develop`. Two removals of unreachable /
redundant UI. No behaviour change beyond removing dead UI. No sim/finalize/
cpu_week_pool/sim_rng changes.

## 1. Account-settings modal + save toast (unreachable)

**Confirmation (grep):** `openAccountSettingsModal` is defined but **never called** anywhere:
```
$ grep -rn 'openAccountSettingsModal' FrontEnd/static
FrontEnd/static/js/shared/authBarInit.js:719:  function openAccountSettingsModal() {   # definition only
```
The auth-bar gear opens the Settings panel (`gobSettings.toggle()`), not this modal. The
bar still *built* the modal + save toast on every page, and shipped their CSS — all dead.

**Call-graph check before removing** (so shared helpers stayed):
- `normalizeAccountSettings` — kept (live at meData processing + `applyGlobalDisplayColor`).
- `.account-switch` CSS — kept (used by `account.html` `#acct-ambience-switch`, and `community.css`).
- `gob:account-settings-updated` was **only dispatched** by the dead modal; its FCC listener
  (`franchise-command-center.js:895`) is left as-is (out of scope; now dormant — noted).

**Removed:**
- `FrontEnd/static/js/shared/authBarInit.js` (1211 → 923 lines): the modal builder, open/close/
  refresh, the save toast (`ensureAccountToast`/`showAccountToast`), and the helpers that became
  exclusively unused (`persistDisplayColor`, `emitAccountSettingsUpdated`, `renderAccountArchetypeBadge`,
  `ensureArchetypeBadgeScript`, `syncAmbienceSwitchFromController`, `applyAmbienceSwitchVisual`,
  `loadMusicController` + `musicControllerPromise`). `initAccountSettingsModal` → `initSettingsButton`,
  stripped to **just the live gear→Settings binding**. The 4 dead `refreshAccountSettingsModal()`
  calls in `initAuthState` removed. `node --check` passes; no dangling references remain.
- `FrontEnd/static/css/auth-bar.css` (918 → 651 lines): the `.account-modal-*` / `.account-field*` /
  `.account-identity` / `.account-avatar` / `.account-username*` / `.account-locked*` /
  `.account-toggle-row*` / `.account-manage-*` / `.account-toast*` rules. **`.account-switch*` kept.**
  Shared `.gob-modal-*` base rules were never here (they live in gob-shell.css etc.) — untouched.
  Braces balance 99/99.
- `tests/e2e/shared-chrome-tokens.spec.js`: removed the `account modal and toast` test that
  force-opened them; the shared switch stays covered by the account-page test.

## 2. Sammy reminder — drop inline ring + light-shell `<style>`; paint from fte.css alone

Follow-up to `reports/tutorials-fte-tokens-2026-10-01.md` §87 ("inline orange ring fallback and the
light-shell `<style>` stay … a later pass could drop both, and fte.css's overrides with them").
`css/fte.css` (restored by that task as the dark Sammy chrome) already outranked the module's
light-shell styling.

**Removed from `FrontEnd/static/js/phaser/utils/pgpcSammyReminderModal.js`:**
- the inline portrait ring (`ringColor` + the `style="border-color…box-shadow…"` on the img) and
  the now-unused `userPrimaryColor` opt;
- the entire inline `<style>` block (backdrop z-index, portrait size, the light-shell "don't show"
  label + `accent-color`).

**Moved into `FrontEnd/static/css/fte.css`** (so it paints from fte.css alone, no longer "overrides"):
- `.pgpc-sammy-reminder-backdrop { z-index: 10040 }` (stacking above the court overlays),
- `.pgpc-sammy-reminder-img { 72px }`, a drop shadow on `.fte-content-img`,
- the full `.pgpc-sammy-dont-show` row (layout + `--text-60` label, `--text-87` hover, neutral
  `--white-90` checkbox) — dropping the high-specificity `.fte-username-backdrop.pgpc-sammy-…`
  outranking prefix that was only there to beat the inline block.

**Proof (before/after shots, `reports/dead-ui-cleanup/`, scroll 0, 1280 + 1920, on `/privacy.html`
which is not `.gob` → exercises fte.css token fallbacks):** `before/after-sammy-{1280,1920}` are
visually identical — same dark modal, portrait (drop shadow preserved; the orange frame is baked
into the Sammy PNG), neutral "don't show" checkbox, "Got It". The thin CSS ring converges from the
inline `#6b7280` to fte.css's neutral `--white-18` (imperceptible against the framed portrait).

## Gates (`.venv/bin/python`)

- **pytest** `--ignore=tests/e2e -q`: **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (230s). 2 XPASS backend/pre-existing; `known_failures.py` not edited.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (real code; new-surface 0/0/0 — fte.css
  additions use tokens + a neutral black drop-shadow, no law colour).
- **`check_migration_gates.py`**: **passed** (Gate A 0/0; Gate B 134/43).
- **Full Playwright** (workers=1, port 8000, foreground under `/tmp/gob-full-playwright.lock`): **825 passed, 7 skipped, 0 failed** (13.7m). `shared-chrome-tokens` passes without the removed account-modal test; all 4 `fcc-fresh-after-game` tests green. `origin/develop` was already current (0 commits ahead; merge was a no-op).

STATUS: COMPLETE. Both unreachable/redundant surfaces removed; all gates green.
