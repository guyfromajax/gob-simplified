# Team Attributes: End of Game vs Training Comparison

Comparison of how each of the **11 core team attributes** (per Team_Attribute_System.md) are changed in:

- **End of Game (EOG)** — `End_Of_Game_System.md` (Franchise mode; after each game)
- **Training** — `Training_System.md` (Franchise mode; user/CPU training sessions)

**Note:** `momentum_score` is legacy and not part of standard init; it is not updated by EOG or Training in the documented flows.

**Attribute ranges (EOG caps):**  
`shot_threshold` 0–200, `rebound_modifier` 0–0.4, `team_chemistry` 7–25, all others -10 to 10.

---

## Comparison Chart

| Attribute | End of Game (EOG) | Training |
|-----------|-------------------|----------|
| **shot_threshold** | **Winning team:** If game FG% > 50%: −(10-20); if FG% > 45%: -(0-10); else +(0,10). **Losing team:** If game FG% > 50%: −(5-15); if FG% > 45%: -(0-5); else +(0,15). | **Scrimmages** (1 pt). By slider points: 0 pts → +(5–15); 1 → −(5–15); 2 → −(10–20); 3 → −(10–30); 4 → −(10–35); 5 → −(10–40). Coaching focus can amplify (e.g. Culture Builder). |

| **discipline** | **Both teams (same criteria):** If team F+TO < opponent's F+TO +(0,1) else -(1,3). | From **player drills** (0.25 pts each): Inside Defense, Outside Defense, Ball Handling, Passing. Team point ranges: 0→(−2,0), 1→(1,2), 2→(2,3), 3→(2,5), 4→(2,6), 5→(2,7). **Authoritarian – Discipline** amplifies gains. |

| **fight** | **Winning team:** +(0,1). **Losing team:** +(−3 to −1). | From **Strength** (0.5 pts) and **Conditioning** (0.5 pts). Same team point ranges as above. **Authoritarian – Discipline** amplifies. |

| **rebound_modifier** | **Both teams (same criteria):** If team TREB > opp TREB + 5: +rand(0, 0.1); if TREB < opp TREB − 5: +rand(−0.1, 0); else +rand(−0.05, 0.05). Capped 0–0.4. | **Rebounding** drill (0.5 pts) and **Scrimmages** (0.5 pts). Rebound drill: 0→−0.05 to −0.01; 1→0 to 0.03; … 5→0.04 to 0.14. Scrimmages: 0→−0.09 to −0.03; 1→−0.03 to 0.03; … 5→0.03 to 0.09. **Authoritarian – Rebounding** amplifies. |

| **offensive_efficiency** | **Both teams:** +(−2, -1). | **Offense Install** slider. Team point ranges: 0→(−2,0), 1→(1,2), … 5→(2,7). **Systems Coach – Offense** amplifies. |

| **defensive_efficiency** | **Both teams:** +(−2, -1). | **Defense Install** slider. Same team point ranges. **Systems Coach – Defense** amplifies. |

| **team_chemistry** | **Score delta** (win score − lose score). &lt;4: win +(1–2), lose +(−2,−1); &lt;10: win +(1–3), lose +(−3,−1); else: win +(1–4), lose +(−6,−2). Capped 7–25. | **Scrimmages** (0.5 pts), **Free Throws** (0.25 pts), **Film Study** (0.25 pts). **Breaks** 4 pts: +(−1,1); 5 pts: +(−3,3). **Culture Builder – Inspire/Teamwork** amplifies. |

| **fb_efficiency** | If FB success rate > 60%: +(0,1); else +(−2,−1). | **Fast Break Offense Install** slider. Same team point ranges. **Systems Coach – Fast Breaks** amplifies. |

| **pt_efficiency** | If (FCP + HCT) combined success rate > 60%: +(1–2); if &lt; 30%: +(−3,−1); else +(−1,0). | **P/T Defense Install** slider. Same team point ranges. **Systems Coach – Presses/Traps** amplifies. |

| **fb_opp_modifier** | If opp FB success rate &lt; 20%: +(0,2); if opp &gt; 55% or opp FB attempts &gt; 12: +(−3,−2); else +(−1,0). | **Fast Break Defense Install** slider. Same team point ranges. **Systems Coach – Fast Breaks** amplifies. |

| **pt_opp_modifier** | If opp (FCP+HCT) combined rate &lt; 20%: +(1–2); if opp &gt; 50% or opp FCP+HCT attempts &gt; 12: +(−3,−2); else +(−2,−1). | **P/T Offense Install** slider. Same team point ranges. **Systems Coach – Presses/Traps** amplifies. |

---

## Summary

- **EOG:** All 11 attributes are updated based on **game stats** (box score, special situations, win/loss, score differential). Same logic for both teams; win/loss and opponent stats drive different outcomes. No user choices.
- **Training:** All 11 attributes can be moved via **drill allocations** (sliders 0–5) and **coaching focus**. Some attributes get points from multiple drills (e.g. discipline from four player drills, rebound_modifier from Rebounding + Scrimmages). Training no longer applies pre-training decay to team attributes; EOG is the performance-based update (per Training_System and End_Of_Game_System).

---

## Simple: Conditions & Ranges

| Attribute | EOG condition | EOG range | Training condition | Training range |
|-----------|---------------|-----------|--------------------|----------------|
| shot_threshold | Win + FG% vs Lose | Win: −(10–20), −(0–10), +(0–10); Lose: −(5–15), −(0–5), +(0–15) | Scrimmages slider 0–5 | −40 to +15 (0 pts: +5 to +15; 5 pts: −10 to −40) |
| discipline | F+TO vs opp F+TO | If team F+TO < opp: +(0,1); else −(1 to 3) | 4 player drills (0.25 pts each) | −2 to +7 |
| fight | Win vs Lose | Win: +(0,1); Lose: −3 to −1 | Strength + Conditioning (0.5 each) | −2 to +7 |
| rebound_modifier | TREB vs opp TREB | −0.1 to +0.1 | Rebounding + Scrimmages (0.5 each) | −0.09 to +0.14 |
| offensive_efficiency | — | −2 to −1 | Offense Install 0–5 | −2 to +7 |
| defensive_efficiency | — | −2 to −1 | Defense Install 0–5 | −2 to +7 |
| team_chemistry | Score delta (win vs lose) | Win: +1 to +4; Lose: −6 to −1 | Scrimmages + FT + Film + Breaks | −3 to +7 (plus Breaks ±1 or ±3) |
| fb_efficiency | FB success rate | −2 to +1 | FB Offense Install 0–5 | −2 to +7 |
| pt_efficiency | FCP+HCT combined rate | −3 to +2 | P/T Defense Install 0–5 | −2 to +7 |
| fb_opp_modifier | Opp FB rate / attempts | −3 to +2 | FB Defense Install 0–5 | −2 to +7 |
| pt_opp_modifier | Opp FCP+HCT rate / attempts | −3 to +2 | P/T Offense Install 0–5 | −2 to +7 |

---

## Source Refs

- **Attributes list & ranges:** `docs/docs_1_systems/06_GMO_Supporting_Systems/Team_Attribute_System.md`
- **EOG rules:** `docs/docs_1_systems/05_GP_Supporting_Systems/End_Of_Game_System.md` (Team Attributes Update System, EOG Data Source & Access Method)
- **Training rules:** `docs/docs_1_systems/06_GMO_Supporting_Systems/Training_System.md` (Drill-to-Attribute Mapping, Team Attributes, Coaching Focus Amplifiers, Pre-Training Conditions)
