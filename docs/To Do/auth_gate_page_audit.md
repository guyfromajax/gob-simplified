# Auth Gate Page Audit

All pages except those in **Public** require authentication.

---

## Public (no auth required)

| Path | Notes |
|------|-------|
| `/homepage.html` | Landing page |
| `/login.html` | Sign in |
| `/signup.html` | Create account |

---

## Protected (auth required)

### Core flow
| Path | Notes |
|------|-------|
| `/mode-select.html` | Choose game mode |
| `/scrimmage-select.html` | Pick teams for scrimmage |
| `/tournament-select.html` | Start or join tournament |
| `/franchise-select-team.html` | Start or join franchise |
| `/set-lineup.html` | Set lineup before game |
| `/court.html` | Live game |
| `/game-plan.html` | Game plan / play calling |
| `/box-score.html` | Box score view |

### Command centers
| Path | Notes |
|------|-------|
| `/tournament.html` | Tournament command center |
| `/franchise-command-center.html` | Franchise command center |

### Rosters & players
| Path | Notes |
|------|-------|
| `/team-roster-view.html` | Team roster (grid/player view) |
| `/team-roster/Bentley-Truman.html` | Team-specific roster |
| `/team-roster/Lancaster.html` | |
| `/team-roster/Four Corners.html` | |
| `/team-roster/Ocean City.html` | |
| `/team-roster/Morristown.html` | |
| `/team-roster/Little York.html` | |
| `/team-roster/Xavien.html` | |
| `/team-roster/South Lancaster.html` | |
| `/team-roster/team-roster-Bentley-Truman.html` | (duplicate pattern) |
| `/team-roster/team-roster-Lancaster.html` | |
| `/team-roster/team-roster-Four-Corners.html` | |
| `/team-roster/team-roster-Ocean-City.html` | |
| `/team-roster/team-roster-Morristown.html` | |
| `/team-roster/team-roster-Little-York.html` | |
| `/team-roster/team-roster-Xavien.html` | |
| `/team-roster/team-roster-South-Lancaster.html` | |
| `/player-detail.html` | Player detail view |

### Plays & coaching
| Path | Notes |
|------|-------|
| `/playbooks.html` | Playbooks |
| `/play-details.html` | Play details |
| `/play-builder.html` | Play builder |
| `/play-builder-v2.html` | Play builder v2 |
| `/plays-builder.html` | Plays builder |
| `/coaching-grid.html` | Coaching grid |
| `/fcp-skeletons.html` | FCP skeletons |
| `/hct-skeletons.html` | HCT skeletons |

### Training
| Path | Notes |
|------|-------|
| `/training.html` | Training |
| `/training-report.html` | Training report |

### Root-level
| Path | Notes |
|------|-------|
| `/index.html` | Redirects to homepage; requires auth |
| `/roster.html` | May be legacy |
| `/player.html` | May be legacy |
| `/games.html` | May be legacy |
| `/index_legacy.html` | Legacy |

### Test pages (optional - may exclude from auth or keep dev-only)
| Path | Notes |
|------|-------|
| `/js/phaser/animation/tests/runBaselineInboundTests.html` | Test page |
| `/js/phaser/animation/tests/runFCPHCTTests.html` | Test page |

---

## Implementation approach

1. **Allowlist**: Public paths = `['/', '/homepage.html', '/login.html', '/signup.html']`
2. **Auth guard**: Include on every page; redirect to `/login.html?redirect=<current-path>` if no `auth_token` and path not in allowlist
3. **Central script**: `FrontEnd/static/js/shared/authGuard.js` – one place to maintain the logic
4. **Script tag**: Added to all HTML files (runs first in `<head>`)

## Implementation status

✅ **Complete** – Auth guard added to all 48 HTML pages. Public pages (homepage, login, signup) remain accessible; all others require `auth_token` in localStorage.
