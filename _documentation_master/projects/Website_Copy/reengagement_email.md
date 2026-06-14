# Re-engagement Email — Copy for Review

Edit the copy below, then tell me to sync it into `BackEnd/utils/reengagement_email.py`.

**How to read the layout:** the body block shows the email exactly as it renders —
a **blank line = a paragraph gap** (visible spacing), and a **single line break = a soft
line break** (no gap). The footer lines sit directly under each other (no gaps).

**Placeholders (injected per-send — keep them, don't hard-code):**
- `{{PLAY_URL}}` → app origin, currently `https://www.geekedoutbasketball.com`
- `{{MAILING_ADDRESS}}` → from env `GOB_MAILING_ADDRESS` (required before send)
- `{{UNSUBSCRIBE_URL}}` → unique per recipient

**Links:** `Play now »` links to `{{PLAY_URL}}`; `Unsubscribe` links to `{{UNSUBSCRIBE_URL}}`.

---

## Subject

```
The new Geeked Out Basketball is here
```

---

## Body (exactly as it renders)

```
Hey Coach,

It's been a minute. While you were gone, we tore the game apart and put it back together better.

Smoother animation that actually feels like basketball. A tutorial system that gets you running fast. Deeper recruiting, practice squads, personalized coaching analysis, a community leaderboard to prove you belong at the top, and much much more.

The court's open. Pick a program, build a roster, and go chase a title.

Play now »

— Jamie

PS — if you've got an old franchise linked to your account, start fresh. The new build is a different game, and you'll want to feel all of it from day one.

──────────────────────────────────────────────

You're receiving this because you have a Geeked Out Basketball account.
Geeked Out Games
1001 S Broad St
Philadelphia, PA 19147
Unsubscribe
```

---

## Notes

- The line of `─` characters represents the divider (`<hr>`) above the compliance footer — it renders as a thin horizontal rule, not literal dashes.
- The three footer lines (account note / address / unsubscribe) are small grey text and stack on consecutive lines with no blank line between them.
- Body paragraphs are normal-size text; each blank line above is real vertical spacing between paragraphs.
