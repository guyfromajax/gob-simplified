# Manual QA Checklist

**Purpose:** Manual testing to verify full functionality before a release or major deploy
**Approach:** Play through the live product flows as a user would
**Estimated Time:** 1-2 hours

> Sunset modes (Single Game, Tournament) were removed from this checklist 2026-06; the live product is Franchise mode plus the FTE tutorial.

---

## Pre-Testing Setup

- [ ] Confirm staging environment is accessible
- [ ] Clear browser cache or use incognito/private window
- [ ] Open browser console to monitor for errors
- [ ] Have Railway logs open for backend monitoring

**Auth (alpha):** When `IS_ALPHA=true`, signup requires an OTP. Optionally verify: signup with OTP, login, and "Forgot password?" / password reset flow.

---

## 1. FTE Tutorial (new-user funnel)

Run with a fresh account (signup → funnel auto-routes).

- [ ] Signup lands on Persona Intro; `LET'S GO` advances to Pick Your Program
- [ ] Team card select opens the Username modal; `CONTINUE` advances to Pre-Game Tip-off
- [ ] `SET LINEUP` lands on tutorial set-lineup with **empty slots**; intro modal + attribute tour fire (once per game)
- [ ] Fill lineup → `RETURN TO GAME` → feedback modal → court loads at Q4 4:00, 60–60
- [ ] Play out the game; EOG shows the "Your Debut" variant (no Box Score button)
- [ ] `Go To Locker Room` → mode-select; debut row appears in the Live Feed (gold border)
- [ ] Refresh mode-select: user is NOT routed back into the funnel (`fte_v2_complete`)
- [ ] Interrupt test: abandon the funnel mid-way, log back in → routed to current step

Reference: `FTE_System.md`.

---

## 2. Franchise Mode

### Setup

- [ ] Create a franchise (or load existing) from mode-select
- [ ] Franchise Command Center loads; all tabs render (Coach's Office, Roster, Standings, Stats, Recruiting, Training, News, Inbox)

### Weekly loop

- [ ] Start the user game for the current week (lineup loads with franchise context)
- [ ] Set lineup and game plan; saves persist after navigating away and back
- [ ] **Play Quarter flow:** after each quarter, "Go To Locker Room" appears; pre-game buttons (Play Quarter / Sim Quarter / Sim Rest of Game) appear for the next quarter; game does NOT auto-start the next quarter
- [ ] **Sim flow:** Sim Quarter / Sim Rest of Game complete quickly and correctly
- [ ] Complete the game; EOG popup shows correct final score; Box Score data is correct
- [ ] Complete the week; FCC updates: record, standings, news headlines, community highlights
- [ ] Verify weekly recruiting + training steps run (points spent, training report)

### Stats & persistence

- [ ] Player stats accumulate week over week (FPD)
- [ ] Refresh the page after a completed game — stats and record still correct
- [ ] Geek points incremented on the user account after a win/loss

### Season edges (when in range)

- [ ] Week 27+ EOS bracket renders; tournament games play correctly
- [ ] Season transition: rosters age, recruits sign, season news clears

---

## Error Handling

- [ ] No critical errors in browser console during normal gameplay
- [ ] No backend errors in Railway logs
- [ ] Missing lineup selections blocked with feedback (can't start a game short-handed)

---

## Performance

- [ ] Set-lineup screen: < 2 seconds to load
- [ ] Game Plan / Playbooks screens: ~1 second to load
- [ ] Sim Quarter: < 5 seconds for a full quarter
- [ ] Game animations: smooth, no lag
- [ ] FCC tab switches: instant (no full reload)

---

## Launch Readiness

- [ ] Staging stable through a full franchise week + FTE run
- [ ] Production environment ready (if deploying)
- [ ] Monitoring in place (Railway logs, Netlify logs, Sentry)

---

## Issues Found

**Document any issues found during testing:**

1. **Issue:** [Description]
   - **Severity:** [Critical/High/Medium/Low]
   - **Steps to Reproduce:** [List steps]
   - **Expected:** [What should happen]
   - **Actual:** [What actually happened]
   - **Status:** [Unfixed/In Progress/Fixed]
