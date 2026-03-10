# Franchise End-of-Season Tournament System

Applies to franchise mode only; does not affect Tournament mode (standalone) tournaments.

## Week map (one tournament round per week)

| Weeks   | Phase              | Description |
|---------|--------------------|-------------|
| 27–29   | Conference         | 16 conference tournaments (8 teams each). R1, R2, Final. |
| 30–31   | Region             | 8 region tournaments (4 teams each). R1 (or bye), then Region Final. Week 30 may have 0 games if all 16 conferences have a double winner (RS#1 + conf tournament winner). |
| 32–34   | National           | 8 region winners. QF, SF, Final. |

## Tiebreakers (no differential)

- **Standings / seeding:** Wins first, then `natl_rank` (lower = higher). Differential is not used.
- **Conference tournament:** Seeded by conference standings after week 26 (W, then natl_rank).
- **Region qualifiers:** Conference tournament winner + conference regular-season #1 (after week 26) per conference. RS#1 tiebreaker: W, then natl_rank.
- **National:** Region champions seeded by W (regular-season only), then natl_rank.

## Conference Tournament

Each regular season concludes with a conference tournament for every conference (16 total). All 8 teams per conference qualify. Single elimination, 3 rounds (QF, SF, Final). Seeding from conference standings (W, natl_rank).

## Region Tournament

Each Region will have a Region tournament consisting of the teams in its two conferences

The team that wins each conference tournamant and the team that was ranked 1 in the converence after week 26 in each conference both quality for the region tournament

Region tournament round 1 matchups will be
-conference tournament winner from one conference vs conference regular season winner from the other conference
-note if the same team wins both the regulars season title and the conference tournament title, they will receive a bye and the two teams who qualified in the other conference will play each other to determine who plays that team in teh region title game
-if both conferences have one team who wins the conference regular season title and the conference tournament title, those two teams will automatically qualify for the region champtionship and there ill be no first round of the region tournament

## National Tournament

- The 8 region tournament winners qualify for the national tournament.
- Teams are seeded by W (regular-season) first, then natl_rank (lowest rank = highest seed).
- Single elimination, 3 rounds (QF, SF, Final) to determine the national champion.


**Tournament Tab in FCC**
-Regular Season: Blank
-Conference Tournament: display conference tournament bracket
-Region Tournament: Region tournament bracket at top, push conference tournemanent bracke to the bottom of the page with a clear horizontal line separating it from the Region Tournament section
-National Tournament: National Tournamen bracket at top, Region tournament inthe vertcial center, and counference tournament at teh bottom, all with clear horizontal lines separating thme from each other.


**Simming Computer Games**
- If the user team was eliminated in the prior EOS week, all games in the current EOS week use the Distant Game Sim engine.
- If the user team is still active:
    - Weeks 27-28:
        - games in the user's conference use the turn-by-turn engine
        - all other conference games use the Distant Game Sim engine
    - Week 29:
        - games in the user's region pair of conferences use the turn-by-turn engine
        - all other conference finals use the Distant Game Sim engine
    - Weeks 30-31:
        - games in the user's region bracket use the turn-by-turn engine
        - all other region games use the Distant Game Sim engine
    - Weeks 32-34:
        - all national tournament games use the turn-by-turn engine
- This sim-routing policy applies in both `complete_week` and `/franchise/sim-rest-of-tournament`.

**Tournament Training**
- Once teams are eliminated, they no longer run training for the remaining weeks. When the user runs training during EOS, computer teams that have lost in any conference/region/national bracket are skipped; only teams still active in tournament play receive template-based (distant) training. Implemented via `get_eliminated_team_ids()` in `franchise_tournament.py` and a skip in the computer-training loop in `run_franchise_training`.
- User EOS eligibility is derived from the current phase bracket, not from a sticky elimination flag. This matters because a user team can lose in the conference tournament and still re-enter as a region qualifier via the regular-season `#1` slot.
- User training / FCC button state therefore uses current-week bracket status:
    - `has_game_this_week`
    - `has_bye_this_week`
    - `eliminated_from_current_phase`
- Example:
    - user loses in conference week 28 -> week 29 shows `Sim Next Round`
    - if that same team qualifies into the region tournament, week 30 derives them as active again from the region bracket and they can resume the normal EOS flow
