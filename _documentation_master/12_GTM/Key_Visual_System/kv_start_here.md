# KV work — start here

Read this first if you are picking up any Geeked-Out Basketball key-visual or
marketing-image work. It exists so no thread has to rebuild context from a conversation.

## The three things you need

1. **This folder** — `_documentation_master/12_GTM/Key_Visual_System/`. The complete,
   self-contained build system: scripts, inputs, and the docs below. **It is canonical.**
   Read `README.md` before touching anything.
2. **`rivals-kv.md`** (here) — every decision and why: the build ladder with measurements,
   the prompting lessons, the casting rationale, the compositing techniques.
3. **`kv_capsules.md`** (here) — the Steam capsule set: what Steam's rules actually
   constrain, why each layout is what it is, and the three defects caught in review.

`DELIVERY_MANIFEST.md` says which built file is live where. Check it before assuming a
rebuild is finished — rebuilding a file changes nothing until it is re-uploaded.

## Canonical vs scratch

`~/Desktop/GOB_KV_test/` on Jamie's Mac is a **working scratch copy**. It has extra
material — round-by-round plates, prompt drafts, contact sheets — that is useful history
and is deliberately not tracked here.

The two have already diverged once, silently and expensively: a copy of `steam.py` was
saved into this folder under the name `cutouts.py`, which both hid the real `cutouts.py`
and left `steam.py` importing itself. Nothing ran. If the two folders disagree, **this one
wins**, and whatever is on the Desktop should be copied here and committed.

## The single irreplaceable file

`source/nb_round5_generation.png` — the raw Nano Banana output. Everything derives from it
and it cannot be regenerated: a re-run is a different roll on the faces and bodies. It is
now tracked in this repo, which is the point of the folder existing. If it is ever lost
from here *and* from the Desktop, the KV is frozen as-is — the finished master survives,
but nothing upstream of it can be changed.

## Five rules that will bite you

1. **One master, everything resampled from it.** Three separate bugs came from reprocessing
   at another size. Every dimension in every script is a fraction of the frame for this
   reason.
2. **Never matte Buckles.** His locs sit under 12 levels from the background; the matte
   slices them off along a straight line, and it is invisible until he is on a brighter
   ground. He goes in as a slab of the master, re-grounded. Only Rozier is matted.
3. **Despill by solving, never by borrowing.** The plate is known, so the true edge colour
   can be solved for. Borrowing a neighbour's colour fails in both directions — too short a
   reach copies the background (black rim), too long copies the wrong material (white halo
   down Rozier's arm). Both shipped before being caught.
4. **Never send anything back to a generator.** Marks, leather and layouts are all
   composited, which is what keeps the faces stable.
5. **If you do re-generate:** every prompt describes the finished picture in absolute
   terms, never as a correction to a previous output. The model sees the plate, not the
   last result.

## Working method that worked

Jamie reviews visually and describes what he sees precisely; the useful response is to
**measure before changing anything**. Most notes in this project turned out to have a
different cause than the obvious one — "too bulky" was arm mass rather than shoulder
width, a cut-looking jersey number was a hardcoded pixel offset, missing hair was a matte
threshold rather than a crop, and a "dark rectangle" was a slab carrying its own
background rather than a feathering problem. Diagnose, then fix, then verify numerically
and show the number.

Two of his notes were correct where the obvious reading was wrong, so take them literally:
if he says an element does not read, the fix is usually to remove it rather than to
strengthen it.

## Repeatable next steps

- Iterating the KV or adding formats → `README.md`, "Making common changes".
- A new Steam capsule or a resize → `steam.py`; `mark_clear()` and `verify()` will catch
  the two failure modes before you look at it.
- A new KV (different players, different staging) → `plate2.py` builds the plate,
  `rivals-kv.md` has the prompt structure and the casting rules.
- Before shipping any new layout that places the slab, run the contrast-stretch check in
  `README.md`. It is how two of the three shipped defects were found.
