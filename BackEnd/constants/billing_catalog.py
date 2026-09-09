"""Product catalogue for Stripe billing — the single source of truth for what is sold.

WHY THIS IS A TABLE AND NOT CODE
--------------------------------
Pricing is not finalised (as of 2026-09-06 the monetisation plan is ~25 days out).
Everything here is expected to change; nothing here should require touching a call
site when it does. Two rules make that hold:

1. **Reference prices by Stripe LOOKUP KEY, never by price ID.** A Stripe Price is
   immutable — changing an amount creates a NEW price with a NEW ``price_...`` id.
   A lookup key is a stable name that can be transferred onto the replacement price,
   so ``founders_edition`` keeps resolving after a repricing with no code change.

2. **SKUs are platform-agnostic.** The same entitlement can be bought on the web
   (Stripe) or, later, on Steam — which is its own payment processor and its own
   tax treatment. So the SKU is the thing; ``stripe`` and ``steam`` are how it was
   acquired. See PurchaseSource.

TAX CODES differ per platform for the SAME product: the web build is streamed
(nothing is downloaded), the future Steam build is downloaded with permanent
rights. That is why tax_code lives per-platform rather than on the SKU.
"""

from __future__ import annotations

from typing import Final


class PurchaseSource:
    """How an entitlement was acquired. Persisted on the user document.

    ``ALPHA`` is the current world: every active user holds full access because the
    alpha is free, not because they bought anything. It is a first-class source so
    that turning monetisation on never has to guess who was grandfathered in.
    """

    ALPHA: Final = "alpha"      # free alpha access — every user today
    WEB: Final = "web"          # bought via Stripe on geekedoutgames.com
    STEAM: Final = "steam"      # bought via Steam (not yet built)
    COMP: Final = "comp"        # manually granted — press, friends, support recovery

    ALL: Final = frozenset({ALPHA, WEB, STEAM, COMP})


# Capabilities an entitlement can grant. These are deliberately coarse: the point is
# to have ONE vocabulary that the app asks about, not to model the final packaging.
# Add to this list freely; changing what GRANTS them is a change in entitlements.py.
class Capability:
    PLAY_FRANCHISE: Final = "play_franchise"
    PLAY_TOURNAMENT: Final = "play_tournament"
    PLAY_SCRIMMAGE: Final = "play_scrimmage"
    RECRUIT_PACKS: Final = "recruit_packs"
    ONLINE_COMMUNITY: Final = "online_community"

    ALL: Final = frozenset({
        PLAY_FRANCHISE,
        PLAY_TOURNAMENT,
        PLAY_SCRIMMAGE,
        RECRUIT_PACKS,
        ONLINE_COMMUNITY,
    })


# ---------------------------------------------------------------------------------
# The catalogue.
#
# ``grants`` is intentionally EMPTY-BY-DESIGN commentary right now: nothing in the
# app consults it yet (see entitlements.py, which returns full access to everyone).
# It is filled in when the monetisation plan lands, and that is the ONLY edit needed
# for the gate to take effect.
# ---------------------------------------------------------------------------------

CATALOG: Final[dict[str, dict]] = {
    "founders_edition": {
        "display_name": "Founder's Edition",
        # Stripe lookup key — set on the price in the Dashboard, transferable across
        # repricings. NOT a price id.
        "stripe_lookup_key": "founders_edition",
        # Web build is played in-browser: streamed, not downloaded.
        "stripe_tax_category": "Digital products > Video games > Streamed > Non-subscription",
        "recurring": False,
        "sources": (PurchaseSource.WEB, PurchaseSource.COMP),
        # TODO(monetisation): fill in once Founder's Edition contents are decided.
        "grants": (),
    },
}


def sku_for_lookup_key(lookup_key: str) -> str | None:
    """Reverse-resolve a Stripe lookup key to our internal SKU.

    Webhooks arrive carrying Stripe's view of the world; this is how that becomes
    our vocabulary. Returns None for an unknown key — which is a real case worth
    logging rather than crashing on, since prices can be created in the Dashboard
    without a corresponding deploy.
    """
    for sku, entry in CATALOG.items():
        if entry.get("stripe_lookup_key") == lookup_key:
            return sku
    return None
