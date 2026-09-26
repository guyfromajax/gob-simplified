# Play GOB on your Mac (first desktop build)

This is the first double-clickable Mac app. It is not the shipping build: no installer, no signing, no auto-update, Mac only.

You will see a splash while the engine starts (the first launch can take a minute). Then Coach Home Base opens. There is no login.

Community, leaderboard, and account panels still try the internet. They will look empty or show errors. That is expected. Offline polish for those is later work.

---

## One-time setup (clean checkout)

1. Install **Python 3.13** if you do not already have it.
2. Clone the repo and get the large files:

   ```
   git clone <the-gob-simplified-url>
   cd gob-simplified
   git lfs pull
   ```

3. Create the Python environment and install the game:

   ```
   python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Install the desktop shell (this folder has its own packages; do not run `npm install` at the repo root):

   ```
   cd desktop
   npm install
   ```

---

## Launch

From `desktop/`:

```
npm start
```

Or make a double-clickable app and open it:

```
npm run pack
open out/GOB-darwin-arm64/GOB.app
```

On an Intel Mac the folder is `out/GOB-darwin-x64/GOB.app`.

The app must stay next to this checkout. It starts the engine from `.venv` in the repo.

---

## What to do

1. Wait for the splash to finish. The first launch copies the real 128-team league into your save, so it can take a little longer.
2. Create a franchise and pick a team.
3. Play a game on the court.
4. Advance a week.
5. Quit from the menu (GOB → Quit). Open it again: the same franchise should still be there.

Your save is a file on this Mac:

`~/Library/Application Support/GOB/local.sqlite`

The first launch copies the real 128-team league (names, colors, mascots, rosters) into that save. If you already played the placeholder league (Lancaster + Team001…), delete that save file first so the real league can load.

---

## If it will not open

**“Port 8765 is already in use”**  
Something else is already using that port — often a leftover GOB engine. The port is fixed on purpose so your settings survive relaunch. Quit the other GOB window, or in Terminal run `lsof -nP -iTCP:8765 -sTCP:LISTEN` and quit that process, then try again.

**Splash then an error screen**  
The engine log is `~/Library/Application Support/GOB/engine.log`.

**Two windows**  
Only one GOB app can be open. A second double-click focuses the first window so two copies cannot write the same save.

---

## Build id

Browse responses carry an ETag that includes the running build. Settings shows the same string as `window.GOB_BUILD_LABEL`. A packaged app has no `.git` directory, so a missing id would stay `unknown` on every version and the Electron cache could keep an old page body after an update.

`scripts/compile_loopback.sh` writes that id before it compiles:

1. Use `GOB_BUILD_ID` if the pack script set it (a version, or `git rev-parse --short=12 HEAD`).
2. Otherwise use the checkout's short git SHA.
3. Write it to `dist/loopback/BUILD_ID` and pass `--include-data-files` so the file sits next to `gob-loopback`.

The Electron shell reads that file (or `GOB_BUILD_ID`) in `desktop/engine.js` and puts the same 12-character value in the engine environment and in `window.GOB_BUILD_LABEL`. Do not ship a binary without this stamp.

## Optional: compiled engine

After `scripts/compile_loopback.sh` has produced a Nuitka binary:

```
GOB_ENGINE_MODE=binary npm start
```

Source mode (`python -m BackEnd.loopback` from `.venv`) is the default and is what you should use first.

---

## Production league check (Jamie, before beta)

This checkout’s league was read from staging. Production is the canonical league. From a machine that can read prod:

```
GOB_DB_ACCESS=read ENVIRONMENT=production MONGO_DB_NAME=gob \
  MONGO_URI='mongodb+srv://…/gob' \
  python scripts/export_base_league.py --target gob \
    --output /tmp/base-league-prod.sqlite --json-output /tmp/base-league-prod.json
```

Compare the printed `version=` to `35e43c9a2970cb105fef35505fbc9536d856392ca0bf88e53758856d54a1a63c`. Same → staging matches prod. Different → ship the prod file as `base_league.sqlite` before beta. Never overwrite the committed file with a scratch path by accident.
