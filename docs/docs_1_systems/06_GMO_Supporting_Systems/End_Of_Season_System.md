## Week 35 Awards And Recruiting

When EOS national week `34` completes, franchise mode advances to week `35`.

### Week 35 Awards

- `Awards` in FCC Resources becomes live at week `35`
- awards are computed once immediately when week `35` begins
- awards persist on the franchise doc in `awards`
- `awards.html` displays 3 All-American teams

### All-American Logic

- use player season stats, not game stats
- use the same scoring logic as Player Of The Game with one change:
  - a player only gets DEF% bonus scoring if `DEFA >= 130`
- 1st Team = top 5 scorers
- 2nd Team = players ranked 6-10
- 3rd Team = uniform random selection of 5 players from ranks 11-20
- selection happens once per season and does not reroll on revisit

### FCC Week 35 State

- top-right CTA copy = `Recruiting`
- CTA click opens `recruiting-orders.html`
- below the CTA, show bold green copy `Recruiting Is Live`
- the old green recruiting-access button is not used for week `35`
- Resources -> Recruits still opens `recruiting.html`

### Week 35 Recruiting

- week `35` is the actual commitment / signing phase
- recruiting-orders page header copy = `Recruiting Focus List`
- week `35` boards use a 20-point recruiting budget
  - `Points Remaining` updates live as the user edits point inputs
- `Save Orders` saves the user board and generates CPU week-35 boards if those CPU boards are still empty
- CPU week-35 orders only generate once per team
- `Run Recruiting` behaves as save-first-then-run
- when `Run Recruiting` finishes:
  - recruiting assignments resolve
  - walk-ons are generated where needed
  - week advances from `35` to `36`
  - user is redirected to `recruiting.html`

## Week 36 Wrap-Up State

- recruiting is closed
- FCC top-right CTA copy = `Go To Next Season`
- CTA uses a confirmation modal
- Resources -> Recruits opens `recruiting.html`, now acting as the signed-results page
- roster pages still show graduating seniors during week `36`
  - append bold green `(GR)` next to their names

## Go To Next Season

When the user confirms `Go To Next Season`:

- current-season game docs for the franchise are deleted
- franchise standings/results are reset
  - `franchise.results` is cleared, so W / L / PF / PA all return to zero for the new season
- seniors are removed from the franchise instance
- signed recruits and walk-ons are carried into the next season
- career stats persist
- season stats reset
- a new franchise-season schedule is generated
- old FRD docs are deleted
- 200 new recruits are generated for the next season
- roster rendering for the next season is franchise-instance driven
  - signed recruits and walk-ons do not need universal `players` docs to appear on roster pages

For the detailed franchise-instance rollover process, see `Season_Init_System.md`.
