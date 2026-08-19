# Franchise End-of-Season Tournament System (**verified 2026-06-13**)

Applies to franchise mode only; does not affect Tournament mode (standalone) tournaments.

> **Scope / lane:** This doc owns the **rules & design** of the EOS tournament — qualification, byes, seeding/tiebreakers, the week-30 bye-modal, FCC tab layout, sim-routing policy, and elimination-skips-training. For the **engineering execution** (bracket write funnel + 409 invariant, start-cpu-sims merge race, `_eos_calendar_advance_update_fields`, region reconcile, phase-b self-heal, the shared `bracket_engine.py`, bracket UI renderer, logging, tests) see `Tournament_Execution_System.md`. For "who writes what" during EOS see `EOS_Write_Path_Inventory.md`.

> Verified vs code: phase week boundaries exact (`franchise_tournament.py` — `EOS_CONFERENCE_WEEKS=(27,28,29)`, `EOS_REGION_WEEKS=(30,31)`, `EOS_NATIONAL_WEEKS=(32,33,34)`, `REGULAR_SEASON_WEEKS=26`); elimination via `get_eliminated_team_ids()` (L1191); bracket-status fields (`has_game_this_week`, `has_bye_this_week`, `eliminated_from_current_phase`) + bye-modal fields (`region_bye_modal_eligible`, `region_bye_modal_seen_season`) present in `franchise_routes.py`; endpoint `/franchise/sim-rest-of-tournament` exists. Training entry point `run_franchise_training` (L10536).

## Week map (one tournament round per week)

| Weeks   | Phase              | Description |
|---------|--------------------|-------------|
| 27–29   | Conference         | 16 conference tournaments (8 teams each). R1, R2, Final. |
| 30–31   | Region             | 8 region tournaments (4 teams each). Week 30 is R1 (or bye); week 31 is every Region Final. Week 30 may have 0 games if all 16 conferences have a double winner (RS#1 + conf tournament winner). |
| 32–34   | National           | 8 region winners. QF, SF, Final. |

## Tiebreakers (no differential)

- **Standings / seeding:** Wins first, then `natl_rank` (lower = higher). Differential is not used.
- **Conference tournament:** Seeded by conference standings after week 26 (W, then natl_rank).
- **Region qualifiers:** Conference tournament winner + conference regular-season #1 (after week 26) per conference. RS#1 tiebreaker: W, then natl_rank.
- **National:** Region champions seeded by W (regular-season only), then natl_rank.

## Conference Tournament

Each regular season concludes with a conference tournament for every conference (16 total). All 8 teams per conference qualify. Single elimination, 3 rounds (QF, SF, Final). Seeding from conference standings (W, natl_rank).

## Region Tournament

Each region has a Region Tournament consisting of qualifiers from its two conferences.

The conference tournament winner and the team ranked first in the conference after week 26 both qualify for the Region Tournament.

Region Tournament first-round matchups:
- The conference tournament winner from one conference plays the regular-season winner from the other conference.
- If the same team wins both its conference regular-season title and conference tournament title, it receives a bye. The two qualifiers from the other conference play to determine its Region Championship opponent.
- If each conference has one team that won both titles, those two teams automatically qualify for the Region Championship and that region has no first-round game.
- Week 30 is reserved for Region Tournament first-round games. A region with two bye teams plays no game in week 30, while other regions still play their first-round games normally.
- All Region Championship games are played in week 31, including championships where both teams earned first-round byes.

### Week 30 User Bye Modal

- Show the Sammy modal only when the user team has a week 30 Region Tournament bye.
- Do not show it when only computer teams have byes or when the user has been eliminated.
- Show it only once per franchise season. The API persists the current season in `region_bye_modal_seen_season`; a new season can qualify independently.
- Eligibility is returned by the command-center API as `region_bye_modal_eligible`.
- Queue it after pending championship moments and wait until other command-center overlays are closed.
- Message: "Hey Coach, congratulations! You won both your conference regular-season title and your conference tournament title. This means you’ve earned a bye in the Region Tournament and have automatically qualified for the Region Championship game. Sim this week’s games, then start preparing for the Region Championship!"
- Primary button: `Sim Region First Round`. It runs the existing `/franchise/sim-rest-of-tournament` week-advance flow.
- Ghost button: `Back to Locker Room`. It closes the modal and leaves the user in the Franchise Command Center.

### Conference Champion Region Qualification Modal

- Show once per season after the user, as its conference tournament's #1 seed, loses in the Conference Tournament. The completed bracket result is authoritative; an unplayed game or a user win does not qualify.
- Eligibility is returned by the command-center API as `conference_rs_region_modal`, including `lost_round` (`round1`, `round2`, or `final`). Presentation is persisted in `conference_rs_region_modal_seen_season` through `PATCH /franchise/conference-rs-region-modal-seen`.
- The first sentence explains that the regular-season conference title still qualifies the team for the Region Tournament.
- After a first-round or semifinal loss, the second sentence tells the user to sim the rest of the Conference Tournament. After a championship loss, it sends the user directly on to the Region Tournament.
- The modal uses the Conference 1 team's Sammy portrait when one exists and the generic white Sammy for every other team.
- Primary button: `Go To Locker Room`. It selects the FCC Home tab when necessary and scrolls to the Locker Room card.

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
- Once teams are eliminated, they no longer run training for the remaining weeks. When the user runs training during EOS, computer teams that have lost in any conference/region/national bracket are skipped; only teams still active in tournament play receive template-based (distant) training. Implemented via `get_eliminated_team_ids()` in `franchise_tournament.py` and an eliminated-team skip in the distant CPU-training helper `_apply_franchise_distant_cpu_training()` (reached through `run_franchise_training`).
- User EOS eligibility is derived from the current phase bracket, not from a sticky elimination flag. This matters because a user team can lose in the conference tournament and still re-enter as a region qualifier via the regular-season `#1` slot.
- User training / FCC button state therefore uses current-week bracket status:
    - `has_game_this_week`
    - `has_bye_this_week`
    - `eliminated_from_current_phase`
- Example:
    - user loses in conference week 28 -> week 29 shows `Sim Conference Tourney Championship`
    - if that same team qualifies into the region tournament, week 30 derives them as active again from the region bracket and they can resume the normal EOS flow
