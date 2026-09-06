"""Stripe billing endpoints.

WHAT IS LIVE HERE: the webhook receiver, and only the webhook receiver.

It verifies Stripe's signature, records the event, and returns 200. It grants
nothing, unlocks nothing, and writes to no user document. That is deliberate: the
endpoint is exposed EARLY so that Stripe can be pointed at production now and
signature verification proven against the real deployment, while the blast radius
of a mistake is still zero. The two classic ways this integration fails — reading a
parsed body instead of raw bytes, and reprocessing redelivered events — are both
things you want to discover with nothing at stake.

NO CHECKOUT ROUTE EXISTS. Creating sessions lives in services/stripe_client.py and
is not reachable from HTTP. Nothing on the site can take a payment.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends

from BackEnd.services.stripe_client import (
    StripeNotConfigured,
    billing_enabled,
    stripe_mode,
    verify_webhook_signature,
)
from BackEnd.utils.auth import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Receive, verify, and record a Stripe event. Side-effect free by design."""
    # Raw bytes — NOT await request.json(). Re-serialised JSON has different bytes
    # and will fail signature verification.
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not signature:
        raise HTTPException(status_code=400, detail="missing stripe-signature header")

    try:
        # Raises on a bad signature; the return value is deliberately unused — the
        # verified raw bytes are what gets persisted below.
        verify_webhook_signature(payload, signature)
    except StripeNotConfigured as exc:
        # Misconfiguration, not a bad request. 503 makes Stripe retry rather than
        # treating the event as permanently rejected.
        print(f"⚠️ [BILLING] webhook unconfigured: {exc}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=503, detail="billing not configured")
    except Exception as exc:
        print(f"⚠️ [BILLING] webhook signature rejected: {exc}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=400, detail="signature verification failed")

    # Store the RAW payload parsed as plain JSON rather than the SDK's Event object.
    # stripe.Event is NOT a dict in stripe-python v15 (`.get()` raises AttributeError,
    # and to_dict_recursive is private), and pymongo cannot encode a StripeObject. The
    # verified bytes are the authoritative record anyway — this keeps what we persist
    # independent of SDK internals across upgrades.
    evt = json.loads(payload)

    # Idempotency by construction: Stripe's event id IS the document _id, so a
    # redelivery is a duplicate-key no-op rather than a second application of the
    # same event. Stripe retries on any non-2xx, so redelivery is normal traffic.
    from BackEnd.db import stripe_events_collection

    already_seen = False
    try:
        stripe_events_collection.insert_one({
            "_id": evt["id"],
            "type": evt.get("type"),
            "created": evt.get("created"),
            "livemode": evt.get("livemode"),
            "received_at": datetime.now(timezone.utc),
            "processed": False,   # nothing consumes these yet — see module docstring
            "payload": evt.get("data", {}),
        })
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
            already_seen = True
        else:
            # Recording failed for a real reason. Return non-2xx so Stripe retries
            # rather than silently dropping the event.
            print(f"❌ [BILLING] failed to record event {evt['id']}: {exc}",
                  file=sys.stderr, flush=True)
            raise HTTPException(status_code=500, detail="could not record event")

    print(
        f"💳 [BILLING] event {evt.get('type')} {evt['id']} "
        f"{'(duplicate, ignored)' if already_seen else 'recorded'} — no action taken",
        file=sys.stderr, flush=True,
    )
    return {"received": True, "duplicate": already_seen}


@router.get("/status")
async def billing_status(user: dict = Depends(get_current_user)):
    """Deploy-verification only: is billing wired, and in which Stripe mode.

    Authenticated because the mode is configuration detail. Returns no secrets.
    """
    return {
        "billing_enabled": billing_enabled(),
        "stripe_mode": stripe_mode(),
        "checkout_available": False,   # no route creates sessions yet
    }
