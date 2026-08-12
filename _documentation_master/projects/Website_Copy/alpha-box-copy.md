# Alpha Box Copy (Mode Select)

Use this file as the source of truth for the "ALPHA RELEASE" box copy shown on the Mode Select screen.

## Current Copy (As Of `FrontEnd/static/mode-select.html`)

Title:
- ALPHA RELEASE

Body (`.alpha-disclaimer-text`):
- **ALPHA ALERT** We have made significant changes to the player attribute system. These changes impact both gameplay and player progression within a season, and from season to season.

If you are mid-season in a franchise, we suggest you delete it and start a new one for the optimal experience.

Thanks for bearing with us during the alpha stage as we make significant and necessary changes to game logic. Once alpha is complete and we enter beta, you will have a more stable build of GOB to play for the long term.

(**ALPHA ALERT** renders in bold red via `.alpha-alert-label`.)

Source:
- `FrontEnd/static/mode-select.html`
- Bump `ALPHA_DISCLAIMER_VERSION` in `FrontEnd/static/mode-select.js` whenever this copy changes so returning users see the box again until they dismiss it.
