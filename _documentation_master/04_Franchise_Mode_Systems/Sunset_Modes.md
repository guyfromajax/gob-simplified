# Sunset Modes — Single Game & Tournament

**Status:** Both modes are sunset (removed from the product surface). Franchise is the only active game mode.

## Decision (June 2026)

If Single Game or Tournament modes return, they will be **rebuilt from scratch on current franchise-era systems**, not revived from the legacy implementations. The legacy code predates most of the engine's modern architecture (UESS animation steps, FTD/FPD persistence, current init patterns) and carries early-process bloat that is not worth maintaining or migrating.

Accordingly:

- **Documentation deleted** (recoverable from git history): `Single_Game_Systems.md`, `Tournament_Mode_Systems.md`, `TCC.md` (all formerly in this folder).
- **Code purge deferred.** Legacy mode code (e.g. `tournament.html` / `tournament.js`, `BackEnd/tournament/` mode routes, `mode="single"` branches) remains in the repo until a dedicated removal pass. Treat it as dead code — do not extend it, and do not let it constrain franchise work.

## Shared assets that live on

These were built for or hardened by the sunset modes and remain live in franchise mode:

- `FrontEnd/static/bracket.js` — `renderBracketShared(...)`, the single bracket renderer; used by the FCC EOS tournament surface (conference / region / national brackets)
- `FrontEnd/static/js/shared/scoutingReport.js` + `BackEnd/utils/scouting_utils.py` — shared scouting-report rendering and play-usage extraction; used by the FCC Scouting Report tab
- `FrontEnd/static/command-center-team-styles.css` — scoped team-report styling used by command-center surfaces
- The franchise EOS tournament's bracket lookup pattern originated in Tournament mode

## Known sunset wiring still flagged elsewhere

Other docs tag remaining sunset-mode wiring inline rather than documenting it fully: `Sound_Design_System.md` (TCC sounds), `Loading_Overlay_System.md` (TCC overlay), `Team_Images_System.md` (sunset surfaces). When the code purge happens, sweep those tags.
