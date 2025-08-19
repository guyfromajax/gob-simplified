# Rebound Animation Defaults

The front-end animation config exposes a `rebound` block in
`FrontEnd/static/js/phaser/animation/animation_config.js`. It controls how
missed shots and putbacks bounce and how players collapse toward the ball.

Default values:

| Key | Default | Description |
| --- | --- | --- |
| `bounceArea` | `{ x: 6, y: 6 }` | Grid offset around the rim where missed shots may land. |
| `playerMoveMs` | `300` | Milliseconds for players to move toward the rebound spot. |
| `attachDelayMs` | `1000` | Delay before the ball attaches to the rebounder after players arrive. |

Overrides can be supplied at runtime via `globalThis.animation_config.rebound`.
Existing behaviours like made shots and free throws use other config values and
are unchanged by these defaults.
