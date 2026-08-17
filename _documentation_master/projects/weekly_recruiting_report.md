## Task
- Publish a weekly recruiting report each week of the franchise season — weeks **1–35** title cadence (Week 1 at season init; completing weeks 1–34 produces Week 2–35 reports). Lean movement includes weeks **27–34**.
- Publish **Season {N} Recruiting Results** after week-35 recruiting runs (user lands FCC at week 36).

## Locked decisions
1. Leans adjust in weeks 27–34 → weekly reports continue through that band.
2. Report titles the **current** week (one ahead of Upset Report for the completed week).
3. Results publish when Run Recruiting finishes → week 36; FCC landing at 36 is OK.
4. Strict sequential ranks; ties broken randomly.
5–6. Omit 0-point teams; lists may be shorter than 25/5.
7. Lean slots 1/2/3 = 100%/50%/25% of current RT, rounded ints.
8. Results: signing team gets 100% of signed recruit RT only.
9. Headline: `Season {N} Recruiting Results` (no week number).
10. Rich `ranking_table` body (National Top 25 + `Region {letter}` Top 5).
11. Real region label e.g. `Region A`.
12. Stable `story_id`s + skip if already present.

## Spec detail
See **Recruiting Reports** in `_documentation_master/04_Franchise_Mode_Systems/News_System.md`.
