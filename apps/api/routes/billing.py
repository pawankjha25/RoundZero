"""
Stripe billing - Phase 2 of the pricing rollout (claude.ai Project
"roundzero" > pricing-design.md): Pay-per-loop, a one-time purchase via
Stripe Checkout, no subscription. Phase 3 (Monthly/Yearly/Founding
subscriptions via Stripe Billing) is not built here.

Two routes:
  POST /v1/billing/checkout - authenticated. Creates a Checkout Session for
    one of PAYPERLOOP_PACKS and returns its URL for the frontend to redirect
    to. Line items are built inline (Checkout's `price_data`) rather than
    referencing pre-created Stripe Price objects in the dashboard - this
    module is then fully config-driven (the pack table below) and needs zero
    manual Stripe dashboard setup beyond getting an API key, matching this
    repo's "no external dashboard configuration required" convention for
    every other provider integration.
  POST /v1/billing/webhook - unauthenticated (Stripe calls this directly,
    not through a logged-in browser session) but signature-verified via
    STRIPE_WEBHOOK_SECRET. Handles checkout.session.completed by crediting
    the purchased rounds (orchestrator.credit_purchase) - see that
    function's docstring for what a completed purchase does to the buyer's
    entitlement. Idempotent against Stripe's at-least-once delivery via
    StripeWebhookEvent (apps/api/models.py).

Both routes degrade safely with no keys set (STRIPE_SECRET_KEY/
STRIPE_WEBHOOK_SECRET unset) - same "unset = clearly not configured, never a
silent 500" pattern as every LLM provider key in apps/api/main.py's
_llm_mode(). /upgrade's Pay-per-loop buttons call checkout and surface
whatever error this returns, so an unconfigured deploy shows "Payments
aren't set up yet" instead of a broken button.
"""
from __future__ import annotations

import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import StripeWebhookEvent, User

router = APIRouter(prefix="/v1/billing", tags=["billing"])
logger = logging.getLogger("roundzero.billing")

# Pay-per-loop packs (pricing-design.md's candidate price points, mid-range
# of each suggested band) - deliberately priced ~2x the subscription's
# effective per-loop rate with almost no bulk discount between the two sizes,
# so this never quietly out-competes Monthly/Yearly (see that doc's "Pay-
# per-loop pricing logic" section). "rounds" counts individual rounds, not a
# literal fixed-size "loop" object - loops in this codebase are variable-
# length (apps/api/schemas.py::LoopCreateRequest), so packs are sized in
# rounds directly rather than assuming every loop is 4 rounds.
PAYPERLOOP_PACKS: dict[str, dict] = {
    "pack_4": {"rounds": 4, "price_cents": 3000, "label": "4 rounds (about 1 loop)"},
    "pack_12": {"rounds": 12, "price_cents": 8000, "label": "12 rounds (about 3 loops)"},
}


def _stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


class CheckoutRequest(BaseModel):
    pack: str


class CheckoutOut(BaseModel):
    checkout_url: str


@router.post("/checkout", response_model=CheckoutOut)
def create_checkout(
    payload: CheckoutRequest, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> CheckoutOut:
    if not _stripe_configured():
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="Payments aren't set up yet - check back soon.",
        )
    pack = PAYPERLOOP_PACKS.get(payload.pack)
    if pack is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unknown pack: {payload.pack}")

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    frontend_url = _frontend_url()
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Round Zero - {pack['label']}",
                            "description": "One-time round pack - no subscription, no expiry.",
                        },
                        "unit_amount": pack["price_cents"],
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{frontend_url}/upgrade?checkout=success",
            cancel_url=f"{frontend_url}/upgrade?checkout=cancelled",
            client_reference_id=user.id,
            customer_email=user.email,
            metadata={"user_id": user.id, "pack": payload.pack, "rounds": str(pack["rounds"])},
        )
    except stripe.error.StripeError as exc:
        logger.exception("Stripe Checkout Session creation failed for user_id=%s pack=%s", user.id, payload.pack)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Could not start checkout - try again in a moment.") from exc

    return CheckoutOut(checkout_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: DBSession = Depends(get_db)) -> dict:
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        # Same "unset = not configured" stance as create_checkout - a
        # webhook endpoint that isn't set up on the Stripe dashboard yet
        # should never be silently accepting unverified payloads.
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Stripe webhook not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook payload/signature") from exc

    # Idempotency - Stripe's delivery guarantee is "at least once," so the
    # same event id can legitimately arrive more than once. Insert first,
    # process only on a clean insert; a concurrent/duplicate delivery hits
    # the same IntegrityError race apps/api/deps.py's user-upsert already
    # handles, and just no-ops rather than double-crediting.
    seen = StripeWebhookEvent(id=event["id"], event_type=event["type"])
    db.add(seen)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "already processed"}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")
        rounds_str = metadata.get("rounds")
        if user_id and rounds_str and rounds_str.isdigit():
            orchestrator.credit_purchase(db, user_id, int(rounds_str))
            customer_id = session.get("customer")
            if customer_id:
                user = db.get(User, user_id)
                if user is not None and not user.stripe_customer_id:
                    user.stripe_customer_id = customer_id
                    db.commit()
        else:
            logger.warning(
                "checkout.session.completed for event_id=%s missing user_id/rounds metadata - not crediting anything",
                event["id"],
            )

    return {"status": "ok"}
