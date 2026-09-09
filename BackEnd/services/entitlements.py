"""The single choke point for "what is this user allowed to do?".

CURRENT STATE: EVERYONE HAS EVERYTHING. Nothing is gated.
=========================================================
This module exists BEFORE monetisation, deliberately. The expensive part of adding
billing to a live product is not taking payments — it is retrofitting a permission
check into dozens of call sites that never had one. Building the choke point while
the answer is trivially "yes" costs almost nothing; building it afterwards means
auditing the whole app.

So: callers ask this module, this module currently says yes, and when the
monetisation plan lands the change is to THIS FUNCTION BODY — not to its callers.

Every active user keeps full access with ``source = "alpha"``. That is a statement
about grandfathering, not a placeholder: alpha users were promised the alpha, and
whatever gate ships later has to keep honouring that without anyone reconstructing
who was here first.
"""

from __future__ import annotations

import os
from typing import Any

from BackEnd.constants.billing_catalog import Capability, PurchaseSource


# Master switch. Default OFF, and read at call time rather than import time so a
# deployment can flip it without a code change. While this is falsy, this module is
# incapable of denying anything — see the early return in get_entitlements().
def _gating_enabled() -> bool:
    return str(os.getenv("BILLING_GATING_ENABLED", "")).strip().lower() in {"1", "true", "yes"}


def get_entitlements(user: dict[str, Any] | None) -> dict[str, Any]:
    """Return the capabilities a user holds.

    Args:
        user: a users-collection document, or None for an anonymous visitor.

    Returns a dict with:
        capabilities: frozenset[str] — what they can do
        source:       str            — how they got it (PurchaseSource)
        gated:        bool           — whether any gating logic actually ran
    """
    # ---- The alpha world -------------------------------------------------------
    # Unconditional full access. This branch is the ENTIRE current behaviour; the
    # code below it is unreachable until BILLING_GATING_ENABLED is set.
    if not _gating_enabled():
        return {
            "capabilities": Capability.ALL,
            "source": PurchaseSource.ALPHA,
            "gated": False,
        }

    # ---- Post-monetisation world (NOT ACTIVE) ----------------------------------
    # Reached only when BILLING_GATING_ENABLED is truthy. Left deliberately
    # permissive rather than restrictive: an unfinished gate must fail OPEN, so a
    # premature flag flip cannot lock paying users out of a game they can play today.
    # Replace this body when the plan is final — and grandfather PurchaseSource.ALPHA.
    if user is None:
        return {"capabilities": frozenset(), "source": None, "gated": True}

    entitlements = user.get("entitlements") or []
    if not entitlements:
        # No purchase record. Today that describes EVERY user, including the ones
        # who have been here since the alpha opened.
        return {
            "capabilities": Capability.ALL,
            "source": PurchaseSource.ALPHA,
            "gated": True,
        }

    held: set[str] = set()
    source = PurchaseSource.ALPHA
    for ent in entitlements:
        held.update(ent.get("capabilities") or ())
        if ent.get("source") in PurchaseSource.ALL:
            source = ent["source"]
    return {"capabilities": frozenset(held), "source": source, "gated": True}


def has_capability(user: dict[str, Any] | None, capability: str) -> bool:
    """Convenience predicate. Currently returns True for any known capability.

    Call this from feature code rather than reading user documents directly — it is
    the seam that makes the eventual gate a one-file change.
    """
    return capability in get_entitlements(user)["capabilities"]
