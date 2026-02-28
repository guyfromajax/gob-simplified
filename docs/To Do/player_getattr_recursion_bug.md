# Player.__getattr__ Recursion Bug (Q4 Simulation)

**Status:** To fix later  
**First seen:** 2/27/2026 (production)  
**Sentry:** Issue ID 7297880340, Project python-fastapi

---

## What Happens

`POST /api/simulate-quarter` fails with **RecursionError: maximum recursion depth exceeded** during quarter 4 simulation. The error occurs in `Player.__getattr__`.

---

## Where the Bug Is

- **File:** `BackEnd/models/player.py`
- **Method:** `Player.__getattr__`
- **Line:** 187 (the line that does `if item in self.attributes:` and uses `self.attributes[item]`)

---

## Proximate Cause (Known Precisely)

When the requested attribute is **`'attributes'`**, `__getattr__` runs (because normal lookup for `attributes` failed). Inside the method, the code accesses `self.attributes` to check `if item in self.attributes`. That lookup again fails and calls `__getattr__(self, 'attributes')` again → infinite recursion.

So the bug is: **`__getattr__` must not access `self.attributes` when `item == 'attributes'`.** The implementation is unsafe for that case.

---

## Root Cause / Trigger (Not Known Precisely)

- **Why did `__getattr__` run?** Some code path did `player.attributes` (or equivalent) on a `Player` instance where the normal `attributes` attribute was not found.
- **Why did that instance lack `attributes`?** Unknown. Possibilities: Player built/loaded without setting it, DB load missing the field, or a different object type (subclass/proxy).
- **Which call site?** Sentry’s recursion stack only shows `__getattr__` repeating. The stack above the first `__getattr__` (the simulate-quarter call that did `player.attributes`) was not in the report, so the exact line that triggered it is unknown.

Fixing `__getattr__` so it does not recurse when `item == 'attributes'` will stop the crash regardless of the trigger.

---

## Sentry Summary (from report)

- **Endpoint:** POST `/api/simulate-quarter`
- **Environment:** production
- **Exception:** `RecursionError` in `Player.__getattr__`; `item == 'attributes'`; `self` repr was broken (likely due to recursion).
- **Tags:** Q4 simulation, after database updates.

---

## Next Steps (when we return to this)

1. Fix `Player.__getattr__` so that when `item == 'attributes'`, it does not access `self.attributes` via normal attribute lookup (e.g. use `object.__getattribute__(self, 'attributes')` or `self.__dict__['attributes']` so the custom `__getattr__` is not re-entered).
2. Optionally: add logging or inspect the simulate-quarter path to find which code accesses `player.attributes` and whether any Player can be constructed or loaded without `attributes` set.
