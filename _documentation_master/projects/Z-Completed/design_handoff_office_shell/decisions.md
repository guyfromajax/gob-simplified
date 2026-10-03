# Decisions to confirm

These were decided during design but weren't in the brief. Confirm each one, or tell the implementer otherwise, before shipping. Items marked **[field]** need a data field that may not exist. Per the handoff rules, the implementer must stop and ask rather than invent it.

## The Office — content
1. **Team RT comparison on Next Game** ("Team RT · LAW A− · MOR B+"). This row was added, and it uses the canonical letter ramp: A blue, B green, C yellow, D/F red. **[field]** opponent team RT.
2. **Player RT digit on each opposing starter** in the projected five at 1920. **[field]** opponent player RT, projected starters.
3. **At 1920 the starting five replaces the separate scorer/rebounder block.** The top scorer and top rebounder carry a small tag inside the five instead. At 1280 only the two leader rows show.
4. **To-dos at 1280 show 4 items** (tasks first, then notes), followed by "See all · N more". At 1920 all items show.
5. **An Advance-mirror tag** ("ADVANCE", neutral outline) marks the to-do that matches the top-bar button. That row routes to the same action.
6. **Gated tasks** get an orange "BLOCKS ADVANCE" tag and an orange checkbox outline. While a task is gated, the top-bar Advance is disabled (neutral, with a lock) and a hint link beside it goes straight to the blocking task: "Assign Practice Squad to continue →". **[field]** a per-task gates-advance flag.
7. **Done to-dos stay clickable** (they open the report or result) at 38% white with a strikethrough.
8. **The "What moved" headline** is rendered as the result card's headline link rather than as a row. It opens the news article. **[field]** a headline per game.
9. **The record cell shows a streak chip** (W4 / L1) instead of a ▲▼ delta.
10. **Team Snapshot colour discipline:** the chemistry meter and attitude bar use neutral white luminance, never the energy hue. Red appears only on the "Unhappy" count when it's above 0.
11. **Attitude labels** Driven / Content / Restless / Unhappy are placeholders. **[field]** Use the game's real attitude buckets and names.
12. **"Moved most this week"** shows the two team measures with the largest absolute delta. At preseason the section reads "Set after camp" with "—" values and no chip.
13. **After a loss:** no team-colour wash, a quiet outlined LOSS badge, both scores in neutral white (loser dimmed), and "Lawrence leader" in place of "Player of the game". The arrival is calm: no count-up and no chip overshoot. At 1920 an "Up next · Scout them" row keeps the card forward-looking.
14. **First week:** the Next Game zone shows the season opener. The Recruiting Wire collapses to one line ("Opens with the invite period · Week 14 · Build your watchlist →"). The opponent's leaders are last season's returning leaders. **[field]**
15. **Signing Day:**
    - The right column is only the Signing Day card; Team Snapshot is hidden.
    - The middle column is the season's final game plus a **Final standings** card (conference table top 5 with your row in navy, plus final rank, conference finish and final record).
    - The Wire is hidden because the targets live in the Signing Day card.
    - Target lean shows as a standing chip: 1st ▲ / 2nd ▼ / T-1st —, plus a short lean line. **[field]**
    - A "Senior Tribute ready" note links to the existing Senior Tribute screen.
16. **The Recruiting rail badge** counts pending recruiting actions (e.g. invites awaiting a decision). It pulses only while a recruiting task gates Advance (Signing Day). **[field]** count + urgent flag.
17. **Stars and film grade** stay neutral (white stars, "Filmed B" as plain text), so letters don't read as team RT.

## Shell
18. **The 1920 density switch is at ≥1680×1000**, driven by JS on the root class. Below that, the 1280 layout stretches fluidly.
19. **Rail hover-expand:** after 400ms of hover, the collapsed rail expands to 200px *over* the page without reflowing it. Otherwise labels come from the `title` tooltip. Tab focus also expands it.
20. **Utility group order:** Tutorials, Feedback, Settings, then a quieter divider and Exit Franchise. When a utility panel is open, its rail item gets a neutral outline, never navy.
21. **Tier top bar:** the emblem sits beside the week stat, the phase label takes the tier metal colour, a 1px metal hairline runs along the bottom edge, and a faint radial glow sits behind the phase. Region and Nationals use emblem.js's region (silver) and national (gold) metals. The phase label reads "Conference Tourney" / "Region" / "Nationals".
22. **The Advance loading state** always reads "STARTING…" whatever the label, with no spinner, and it ignores repeat clicks. Disabled is neutral grey with a lock and always has a hint link.
23. **Section pages:** the page title and sub-tabs are sticky together, and the table header sticks directly below them.
24. **Max content width is 1664px**, centred, on viewports wider than 1920.

## Settings
25. **Panel, not modal.** It's anchored to the gear, 440px wide, slides in over the page with a 62% scrim, and the top bar and rail stay visible. The reasons:
    - Audio applies live, so there's no Save button and no orange.
    - You can hear changes in context.
    - It opens the same way from every franchise page.

    It closes with ×, Esc, a click on the scrim, or the gear again.
26. **Mute sits left of each slider.** A muted row keeps its level (dimmed), so unmuting restores it.
27. **Offline:** the Account section is replaced by a one-line note. The footer shows the connection state, and the rail drops Feedback.
28. **Log Out** is the standard ghost secondary button: not red, and no confirmation.
29. **Coach stats tiles** link to a coach profile page. **[field / route]** Confirm it exists.

## Gameplay
30. **The speaker sits in the right-hand cap of the existing scoreboard strip** at 38% white. The popover holds only a **Mute all** switch (navy when on) plus Music and SFX sliders. The game never pauses while it's open. When muted, the icon shows a slashed speaker at 60%, so the state is visible without opening the popover.
31. **The scoreboard strip in the reference frame is generic.** Keep the real one; only the speaker cap and popover are specified.
