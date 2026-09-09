"""Stripe SDK access — configured, centralised, and inert until keys are present.

WHY EVERY CHECKOUT MUST GO THROUGH create_checkout_session()
-----------------------------------------------------------
Managed Payments (Stripe's merchant-of-record product) is NOT an account-wide mode.
Accepting its terms only makes it AVAILABLE; merchant-of-record status is opted into
per transaction via ``managed_payments.enabled``. A Checkout Session that omits the
flag silently runs as classic Stripe — with Geeked-Out Games as merchant of record
and therefore personally liable for VAT/sales-tax registration and remittance in
every jurisdiction it sold into. There is no error and no warning; it surfaces at
tax time.

So the flag is set HERE, once, and nothing else in the codebase is permitted to
build a Checkout Session. That is the whole reason this function exists.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# The SDK is an optional import on purpose: the app must boot fine on a machine
# (or a test run) where Stripe is neither installed nor configured.
try:
    import stripe as _stripe
except ImportError:  # pragma: no cover - exercised only where the dep is absent
    _stripe = None


# Pin the API version so a Stripe-side upgrade cannot change behaviour underneath a
# running deploy. Left unset by default rather than hardcoding a guess: read the
# account's current version from Dashboard -> Developers -> API version, then set
# STRIPE_API_VERSION to it. Unset means "whatever the account default is today",
# which is convenient and NOT reproducible.
STRIPE_API_VERSION = os.getenv("STRIPE_API_VERSION") or None


class StripeNotConfigured(RuntimeError):
    """Raised when a Stripe call is attempted without a secret key."""


def billing_enabled() -> bool:
    """Whether the paid purchase path is exposed at all.

    Default OFF. This gates CHECKOUT, not the webhook receiver — see billing_routes:
    the webhook is deliberately live early so Stripe can be pointed at it and
    signature verification proven in production while it still does nothing.
    """
    return str(os.getenv("BILLING_ENABLED", "")).strip().lower() in {"1", "true", "yes"}


def stripe_mode() -> str | None:
    """'test', 'live', or None — inferred from the secret key prefix."""
    key = os.getenv("STRIPE_SECRET_KEY") or ""
    if key.startswith("sk_test_"):
        return "test"
    if key.startswith("sk_live_"):
        return "live"
    return None


def get_client():
    """Return the configured stripe module, or raise StripeNotConfigured.

    Never returns a half-configured client: callers can assume a returned object
    has a key set.
    """
    if _stripe is None:
        raise StripeNotConfigured("the 'stripe' package is not installed")
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    _stripe.api_key = key
    if STRIPE_API_VERSION:
        _stripe.api_version = STRIPE_API_VERSION
    return _stripe


def resolve_price_id(lookup_key: str) -> str:
    """Resolve a stable lookup key to the price id Stripe wants at call time.

    Prices are immutable — repricing creates a new price and the lookup key is
    transferred onto it. Resolving at call time is what makes a price change a
    Dashboard action rather than a deploy.
    """
    client = get_client()
    prices = client.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if not prices.data:
        raise StripeNotConfigured(f"no active Stripe price for lookup key {lookup_key!r}")
    return prices.data[0].id


def create_checkout_session(
    *,
    lookup_key: str,
    user_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Create a Checkout Session with merchant-of-record ALWAYS on.

    NOT REACHABLE FROM ANY ROUTE YET. No endpoint calls this; it exists so the
    correct shape is fixed before the purchase flow is designed.

    ``user_id`` is threaded through as BOTH client_reference_id and metadata so the
    webhook can attribute the purchase to a GOB account. Matching on email instead
    breaks whenever someone pays with a different address than they signed up with,
    which for a game whose product IS the entitlement means a manual support ticket.
    """
    if not billing_enabled():
        raise StripeNotConfigured("BILLING_ENABLED is not set; refusing to create a session")

    client = get_client()
    return client.checkout.Session.create(
        mode="payment",
        line_items=[{"price": resolve_price_id(lookup_key), "quantity": 1}],
        # ---- the load-bearing line: merchant of record --------------------------
        managed_payments={"enabled": True},
        client_reference_id=user_id,
        metadata={"gob_user_id": user_id, "sku_lookup_key": lookup_key, **(metadata or {})},
        customer_email=customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
    )


def verify_webhook_signature(payload: bytes, signature_header: str):
    """Verify and parse a webhook payload. Returns the Stripe Event.

    ``payload`` MUST be the raw request body. Parsing to JSON and re-serialising
    changes the bytes and the signature will not verify — the single most common
    way this integration is gotten wrong.
    """
    client = get_client()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is not set")
    return client.Webhook.construct_event(payload, signature_header, secret)


def log_configuration_at_boot() -> None:
    """One line at startup so a deploy's billing posture is visible in the logs."""
    mode = stripe_mode()
    print(
        f"💳 [BILLING] enabled={billing_enabled()} mode={mode or 'unconfigured'} "
        f"api_version={STRIPE_API_VERSION or 'account-default'}",
        file=sys.stderr,
        flush=True,
    )
