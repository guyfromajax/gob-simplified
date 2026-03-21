# Training Notes System

Training Notes appear in the Training Report after each week’s training run. Content is published **under fixed section headers**. If nothing qualifies for a section, print **“No Significant Updates”** under that header (**confirmed** for every section).

**Training Report page order** (`training-report.html`): **Notes** → **Player Report** (grid) → **Team Report** (team attribute changes) → **Playbook Summary** (plays).

---

## Shared definitions

- **Player cumulative attribute change:** Sum of that player’s per-attribute deltas from training (same basis as the report’s player change breakdowns).
- **Team-wide attribute change:** For each attribute code, **sum of that attribute’s deltas across all roster players** (not team-level `team_changes` unless specified elsewhere).
- **Post-training values:** Unless noted, use state **after** training (e.g. CH for locker room roll, effectiveness for plays/defenses).
- **Training Camp vs non–Training Camp:** Training Camp notes apply to the franchise **first training / training camp** run; **Non Training Camp** notes apply to all later weekly trainings (same code flag as `is_training_camp` / skip pre-training path).

---

## Training Camp notes

### Training Camp MVP

- List the player(s) with the **largest positive** cumulative attribute gain.
- **Names only** — do not print total gain.
- One leader → header **“Training Camp MVP”**.
- Tie for the lead → header **“Training Camp Co-MVPs”** and list all tied players.

### Biggest Concern

- Among players with cumulative increase **&lt; 10**, list the **smallest** increase (worst “gainer”).
- If **no** player has cumulative increase &lt; 10 → **“None”**.
- One player → **“Biggest Concern”**; multiple tied → **“Biggest Concerns”** and list all.

### Most Positive Locker Room Influence

- Randomly select one player with **post-training CH &gt; 59**.
- If none qualify → **“None”**.
- Weighting: players with **CH &gt; 79** have **2×** the chance of players with **CH 60–79**.

### Strong Cumulative Increase

- List every attribute whose **team-wide sum of deltas** is **> +49**.

### Concerning Progression

- List every attribute whose **team-wide sum of deltas** is **< +21**.

### Strongest Offensive Plays

- Use **post-training effectiveness** (not deltas).
- Order plays by effectiveness (highest first). Group plays that share the same effectiveness into **tiers**.
- **Greedy rule (max three names total):** Walk tiers from top downward. For each tier, if **(already listed count) + (plays in this tier) &gt; 3**, **skip the entire tier** (do not name any of them). Otherwise add **all** plays in that tier to the list.
  - Example: one play alone in tier 1 → list it; tier 2 has four tied → 1 + 4 &gt; 3 → skip tier 2 entirely (only one play named).
- If **no** plays are listed after this (e.g. four-way tie at the top tier), the section is **“No Significant Updates”** (same as other empty sections).

### Strongest Defensive Set

- Use **post-training effectiveness** on defensive sets (scouting).
- List the defense(s) with the **highest** effectiveness; **all** tied for that top value.

### Fast Break Readiness

Let **S** = `fb_efficiency` + `fb_opp_modifier` (post-training team values).

| Label        | Condition |
|--------------|-----------|
| **Very Strong** | S &gt; 11 |
| **Strong**   | 4 ≤ S ≤ 11 |
| **Neutral**  | -3 ≤ S ≤ 3 |
| **Weak**     | -11 ≤ S ≤ -4 |
| **Very Weak** | S &lt; -11 |

*(If S falls in a gap between bands — e.g. non-integer edge cases — implementation should follow the same numeric boundaries; team attrs are typically integral.)*

### Press/Trap Readiness

Same band table as **Fast Break Readiness**, but **S** = `pt_efficiency` + `pt_opp_modifier`.

---

## Non Training Camp notes

### Practice Player Of The Week

- Same rules as **Training Camp MVP**, with headers **“Practice Player Of The Week”** / **“Practice Players Of The Week”**.

### Biggest Regression

- Player(s) with the **largest negative** cumulative change; must have **negative** cumulative total.
- If no player is negative → **“None”**.
- Ties: list all; **do not** change the header.

### Most Positive Locker Room Influence

- Same as Training Camp (post-training CH, weighted random).

### Strong Cumulative Increase

- List every attribute whose **team-wide sum of deltas** is **≥ +10**.

### Concerning Regression

- List every attribute whose **team-wide sum of deltas** is **≤ -10**.

### Strongest Offensive Plays / Strongest Defensive Set / Fast Break Readiness / Press/Trap Readiness

- Same rules as Training Camp sections above.

---

## Deferred (not v1 implementation)

### Anticipated Crowd Support

**Out of scope for initial implementation** — depends on projecting Home Crowd / Community Engagement / chemistry bands; will be revisited later.

---

## Player Energy Levels *(both TC and non-TC)*

**Always last** among Training Notes sections (after all sections above).

- Reuse **existing** training copy for conditioning / scrimmages NG effects (e.g. reduced energy next game — same strings as today’s `training_notes` energy lines).
- If there are **no** such messages for this session, print **“No Significant Updates”** under this header (consistent with global rule).

---

*Last updated: boundaries, team sums, offensive tie cutoff, defensive confirmation, Crowd Support deferred, Player Energy Levels section added.*
