# agents_update.md

## Recommendation

`docs/agents.md` should be expanded and refocused. It is currently useful, but it is weighted heavily toward animation concepts and does not capture enough of the cross-system rules that matter for safe feature work in this repo.

## What To Add

### Canonical Sources of Truth

Add a section that explicitly defines canonical fields and ownership by subsystem.

Examples:
- `natl_rank` is the canonical franchise team rank field
- `rank` is only a response alias where explicitly mapped
- game docs use canonical `team_id` strings
- franchise master stores use ObjectId linkage

This would reduce ambiguity when implementing UI features that depend on ranks, team identity, or mixed persistence layers.

### UI Feature Change Rules

Add rules for how to implement small frontend features safely.

Recommended guidance:
- If a UI field is canonical data, prefer updating the backend contract instead of deriving it locally in the page
- Filtering must happen before ranking and before limiting when a page promises a scoped top N
- Explicitly define whether a displayed rank is absolute or relative

This would have prevented the recent stats-page issues.

### Don’t Break Existing Contracts Checklist

Add a short checklist to use before finishing micro-features.

Suggested items:
- What system owns the source of truth for this field?
- What existing behavior must remain unchanged?
- Is this a frontend-only change, or does it require a backend contract update?
- What adjacent views or tabs should be re-verified?

### Stats / Rank / Leaders Rules

Add a subsection covering the stats page specifically.

Suggested rules:
- `stats.html` Rank uses canonical `natl_rank`
- Conference and Region tabs display absolute national rank, not within-scope rank
- National `Top 25` filtering affects Team Stats only, not Leaders
- Leaders cards must show the true top 10 within the selected scope
- Scope filtering occurs before limiting

### Navigation State Rules

Add a subsection for FCC navigation behavior.

Suggested rules:
- FCC tab state lives in the URL
- `return_url` is the canonical return contract for FCC-launched pages
- pages not launched from FCC fall back to default FCC landing behavior

This would help preserve consistency for “Back To Locker Room” behavior.

## What To Remove Or Move

The current `agents.md` is more animation-specific than its title suggests. I would either:

- trim the animation detail and link out more aggressively to dedicated animation docs, or
- keep the animation overview but move lower-level implementation detail into the animation system documentation

The goal would be to make `agents.md` function more like a repo-wide engineering playbook than a subsystem reference.

## Main Takeaway

The most valuable improvement is to evolve `docs/agents.md` from a mostly conceptual engine reference into a practical guide for modifying the codebase safely.

The biggest missing guidance today is:
- canonical data ownership
- scoped query rules
- frontend-vs-backend responsibility boundaries
- verification expectations for micro-features

Those additions would directly reduce the kind of regressions and ambiguity we hit during recent stats and FCC work.
