# PCPG — Language rules for press conference copy

## Macro objective

Press conference text should feel like **real sports media**: a reporter asks a sharp, natural question; the coach answers in **plain, spoken English**. Players should **never** feel like they are reading marketing copy, UI tooltips, or a design doc. The goal is **believable voice first**, **systems second**. **Pipeline mechanics** (triggers, shuffle, session API) live in `docs/docs_1_systems/06_GMO_Supporting_Systems/Press_Conference_System.md` and the code. **This file** still holds **copy contracts** the game enforces or strongly expects (names, pronouns, placeholders)—so authors and reviewers don’t have to read Python.

---

## Voice

- **Organic human voice:** Write how people actually talk at a podium or in a scrum—contractions when they fit, varied sentence openings, occasional fragments where they sound natural. Avoid template-y rhythm (“We need to X. We need to Y. We need to Z.”).
- **Reporter questions** should sound like one beat writer or sideline reporter, not a committee. One clear angle per question.
- **Coach answers** stay in **first person** (“I”, “we”, “our guys”) and sound like something a coach could say out loud without reading.

---

## Brevity

- **Paramount for every multiple-choice answer.** If an answer runs long, cut adjectives, parallel clauses, and repeated ideas before touching the core claim.
- **Target:** answers should usually be **one single punch sentence that clearly states the idea and tone of the aswer -- two sentences in rare occassions where we have no choice to get the idea across**. If it fills more than **~2 lines** in a typical modal width, trim, except for rare exceptoins that a third line is necessary to get the idea across.
- **Questions** can be slightly longer than answers when the setup needs context, but **one question = one idea**. No stacked unrelated prompts (“What worked, and what does it mean for recruiting, and how do you fix the turnovers?”).
- **Lead with the point.** Front-load the takeaway; trim throat-clearing (“I think at the end of the day…”).
- **Questions need to state the context clearly.** You cannot assume the user knows specfic team or player stats because  at this point they have not read the box score, they have just finished playing the game and gone straight to the press conference. So if a reporter is asking a question about a player who fouled out or scored a lot of points, that needs to be present in the question. Example, "Kwame Castor led your team in scoring with 32 points tonight. Was that part of your game plan or did it happen organiclly with game flow?"

---

## Clarity and consistency

- **One referent per pronoun chain.** Don’t let *they/them* hop between “your star,” “the bench,” and “the opponent” in the same sentence. Prefer **he/him** when the stem and franchise voice assume a male player, or **name the group** (“your bench,” “their guards”) when plural.
- **Match the stem.** If the question says *his* night, don’t answer with a vague *they* that sounds like the wrong group.
- **Numbers and facts** in copy should match what placeholders will inject; don’t contradict the box score in fixed wording.

---

## Player reference rules (question ↔ answers)

These align with how PGPC **substitutes** text today; write the bank so behavior stays predictable.

### When the question is about **one** featured player

- **Singular pronouns for that player in answers** — Prefer **he / him / his** when the franchise/player presentation matches that convention and the stem is about an individual. Don’t use **they / them** for the same player in answers if the question used **he / his** or a single `{player_name}`: it reads like a different antecedent (teammates, “people,” generic players).
- **Name in answers vs question** — If the stem includes **`{player_name}`**, the live question shows the player’s **full name**. Answers that repeat the name are rewritten to **first name only** when the full name is **two or more words** (e.g. “Jordan Smith” → “Jordan” in answers). **Single-word** names stay as-is. Author answers so they still sound natural with **first name** (or without repeating the name every line).

### When the question is **not** about one person

- **Team, opponents, or several players** — Plural **they / them**, **we / our guys**, or naming the group is appropriate. Keep **one clear referent** per sentence (see **Clarity and consistency**).

### Optional explicit name in answers

- You may still write `{player_name}` in an answer string if needed; it will get the same **first-name** treatment when the question used `{player_name}` and the name is multi-word. Prefer lean copy: often **he/him** or one first-name beat is enough.

---

## Archetypes (tone, not jargon)

Answers carry an **archetype** for flavor and systems. The writer should **embody** that voice without naming it:

| Archetype | Lean into |
|-----------|-----------|
| **Authoritarian** | Standards, accountability, non-negotiables—still human, not a drill sergeant caricature. |
| **Systems coach** | Scheme, reads, execution, film—concrete, not buzzword soup. |
| **Player maximizer** | Individual growth, confidence, specific development—avoid empty praise. |
| **Culture builder** | Locker room, belief, togetherness—earned, not saccharine. |
| **Neutral** | Plain, low-drama—**especially** keep these **short**; they’re often the “straight” option. |

Archetype is **not** an excuse for long answers. **Short beats colorful.**

---

## Contrast among multiple-choice answers

Archetype labels are a **backend hook** (voice + effects), but **players experience options as different coaching moves**—what you believe, how hard you lean, whether you engage the premise. **Every set of answers should spread across that space**, not five minor wordings of the same take.

**Aim for a mix** (not every question needs all of these, but the *spread* should be obvious):

- **Coaching / system angle** — e.g. protect the player vs hold the standard vs it’s a scheme/read issue vs “we win as a team, stats are noise.”
- **Emotional tone** — warm vs blunt vs frustrated vs flat and professional.
- **Answer type** — fully buys the question’s frame vs **deflects or challenges** the question (“I’m not going to pin that on one guy tonight”) vs noncommittal bridge.

**Example** (illustrative): the stem is about a **highly rated player who didn’t score much**.

| Stance | What the player should *feel* |
|--------|--------------------------------|
| **Supportive** | You’ve got his back; the night was context, matchups, or flow—not a verdict on him. |
| **Frustrated / demanding** | You expect more from a player with that profile; it wasn’t good enough. |
| **Dismissive of the question** | You’re not giving the premise oxygen—small sample, wrong focus, next game. |
| **Neutral** | Straight, low-drama summary: what happened factually without a heavy moral. |

Those four are **different decisions**, not four archetype skins on one paragraph. When authoring, ask: **If someone only read the answers (not the letters), would they clearly see different coaches or different moods?** If two options collapse into the same choice, rewrite one until they diverge.

**Still keep brevity:** contrast comes from **angle**, not from **length**.

---

## Placeholders (copy-only reminders)

- **`{player_name}`** — See **Player reference rules** above (full name in question; first name in answers when multi-word).
- **Don’t use jersey numbers** in copy; the product doesn’t inject them.
- Other tokens (`{opponent_name}`, streaks, stat gaps, etc.) should read smoothly when replaced by real values—**no fixed phrasing that only works for wins or blowouts** unless the trigger guarantees that situation.

---

## Review checklist (before shipping new copy)

1. **Read aloud**—question and each answer. Anything that sounds read instead of spoken gets cut.
2. **Answer length**—longest option still lean? If not, shorten the longest first.
3. **Pronouns & player focus**—single player in the stem → singular in answers for that player? Name shortened correctly in answers?
4. **One idea** per question; **one clear stance** per answer.
5. **Contrast**—do the options differ by angle, tone, or answer type, not just synonym swaps?

---

*Living doc for authors and reviewers. Pipeline / API: `Press_Conference_System.md`.*
