##Objective
Build a slideshow celebrating each graduating senior as the user progresses from one season to the next. This triggers when the user presses the Go To Next Season action button in the FCC and will play in lieu of the load screen that currently plays in that scenario.

##Slideshow progression
Animate this similar to how we animate recruiting reveals, but with some differences.
- No leaderboards as this is not recruiting
- Make the player iamge the prominent hero, not the team logo. This is because in recruiting results, the signing team is a major reveal. Where as in this progression the player and his career results are teh focus and his team is already known.
- Hold each player on screen for 6000ms

##Per player content
-Headshot
-Career stats
    - Per game: points, rebounds assists
    - Career DEF%
    - Number of titles won
        - Conference Regular Season
        - Conference Tourney
        - Region Tourney
        - National Tourney

##Once all players have aniated
- Land on a resuloution screen showing all players, each with their own row of their headshot, name, stats and titles
- User presses "Advance To Next Season" button on this screen to advance to teh next sesaon FCC
- If the next season is still loading, show our current load screen until it's ready

##If a team has no graduating seniors
- Simply show our current season transition load screen experience

##Shipped decisions
- Sequence: snapshot tribute → start `finish-season` in the background → slideshow → resolution → Advance (load cover only if rollover is still running).
- Tribute set: user-team **active-roster** seniors/graduates only. Training squad, practice squad, and cuts are out. Order is RT descending. 6000ms hold. No skip/pause.
- Titles are player-specific on `fpd.titles` (`conf_rs`, `conf_t`, `region`, `national`). Incremented on the user team's active roster when a title is awarded. Future-forward only; no historical backfill. Hide a kind when its count is 0.