"""
Zero Latency Billing Module
Stripe integration for subscription management.
"""
import os
import sys
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional

from api.auth import require_jwt, _db_exec

logger = logging.getLogger("zerolatency.billing")

# ─── Stripe Configuration ───────────────────────────────────────────────────

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

SITE_BASE = os.environ.get("SITE_BASE_URL", "https://0latency.ai")
API_BASE = os.environ.get("API_BASE_URL", "https://api.0latency.ai")

# ─── Plan Configuration ─────────────────────────────────────────────────────

PLAN_CONFIG = {
    "pro": {
        "price_id_monthly": os.environ.get("STRIPE_PRO_PRICE_ID_MONTHLY", ""),
        "price_id_yearly": os.environ.get("STRIPE_PRO_PRICE_ID_YEARLY", ""),
        "product_id": os.environ.get("STRIPE_PRO_PRODUCT_ID", ""),
        "memory_limit": 50000,
        "rate_limit_rpm": 60,
        "agent_limit": 5,
    },
    "scale": {
        "price_id_monthly": os.environ.get("STRIPE_SCALE_PRICE_ID_MONTHLY", ""),
        "price_id_yearly": os.environ.get("STRIPE_SCALE_PRICE_ID_YEARLY", ""),
        "product_id": os.environ.get("STRIPE_SCALE_PRODUCT_ID", ""),
        "memory_limit": -1,  # unlimited
        "rate_limit_rpm": 120,
        "agent_limit": -1,  # unlimited
    },
}

FREE_LIMITS = {
    "memory_limit": 100,
    "rate_limit_rpm": 30,
    "agent_limit": 1,
}

# Map price_id back to plan name for webhook handling
PRICE_TO_PLAN = {}
for _plan, _cfg in PLAN_CONFIG.items():
    if _cfg["price_id_monthly"]:
        PRICE_TO_PLAN[_cfg["price_id_monthly"]] = _plan
    if _cfg["price_id_yearly"]:
        PRICE_TO_PLAN[_cfg["price_id_yearly"]] = _plan


# ─── Cached Stripe prices ────────────────────────────────────────────────────

_cached_prices = None
_cached_prices_at = 0


def _fetch_stripe_prices():
    """Fetch prices from Stripe and cache them. Returns plan config with live prices."""
    global _cached_prices, _cached_prices_at
    import time as _t

    # Cache for 5 minutes
    if _cached_prices and (_t.time() - _cached_prices_at) < 300:
        return _cached_prices

    plans = {}
    for plan_name, cfg in PLAN_CONFIG.items():
        plan_data = {
            "name": plan_name,
            "memory_limit": cfg["memory_limit"],
            "rate_limit_rpm": cfg["rate_limit_rpm"],
            "agent_limit": cfg["agent_limit"],
            "monthly": None,
            "yearly": None,
        }
        for interval, key in [("monthly", "price_id_monthly"), ("yearly", "price_id_yearly")]:
            price_id = cfg.get(key)
            if price_id:
                try:
                    price = stripe.Price.retrieve(price_id)
                    plan_data[interval] = {
                        "price_id": price_id,
                        "amount": price.unit_amount,  # in cents
                        "currency": price.currency,
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch price {price_id}: {e}")
        plans[plan_name] = plan_data

    _cached_prices = plans
    _cached_prices_at = _t.time()
    return plans


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def get_plans():
    """Public endpoint — returns available plans with live Stripe prices."""
    plans = _fetch_stripe_prices()
    return {
        "plans": plans,
        "free": FREE_LIMITS,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_stripe_customer(user_id: str) -> str:
    """Get existing or create new Stripe customer for user."""
    rows = _db_exec("""
        SELECT p.stripe_customer_id, au.email, p.name
        FROM memory_service.profiles p
        JOIN auth.users au ON au.id = p.id
        WHERE p.id = %s::UUID
    """, (user_id,))
    if not rows:
        raise HTTPException(404, detail="User not found")

    stripe_customer_id, email, name = rows[0]

    if stripe_customer_id:
        return stripe_customer_id

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata={"user_id": user_id},
    )

    _db_exec("""
        UPDATE memory_service.profiles SET stripe_customer_id = %s WHERE id = %s::UUID
    """, (customer.id, user_id), fetch=False)

    logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
    return customer.id


def _get_subscription(user_id: str) -> dict | None:
    """Get active subscription for user."""
    rows = _db_exec("""
        SELECT id, stripe_customer_id, stripe_subscription_id, plan, status,
               current_period_start, current_period_end, created_at, updated_at
        FROM memory_service.subscriptions
        WHERE user_id = %s::UUID
        ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    if not rows:
        return None
    r = rows[0]
    return {
        "id": str(r[0]),
        "stripe_customer_id": r[1],
        "stripe_subscription_id": r[2],
        "plan": r[3],
        "status": r[4],
        "current_period_start": str(r[5]) if r[5] else None,
        "current_period_end": str(r[6]) if r[6] else None,
        "created_at": str(r[7]),
        "updated_at": str(r[8]),
    }


def _resolve_plan_from_subscription(stripe_subscription_id: str) -> str:
    """Determine plan name from Stripe subscription's price ID."""
    try:
        sub = stripe.Subscription.retrieve(stripe_subscription_id)
        items = sub.get("items") if isinstance(sub, dict) else getattr(sub, "items", None)
        if items:
            items_data = items.get("data") if isinstance(items, dict) else getattr(items, "data", [])
            if items_data and len(items_data) > 0:
                item = items_data[0]
                price = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
                price_id = price.get("id") if isinstance(price, dict) else getattr(price, "id", None) if price else None
                if price_id and price_id in PRICE_TO_PLAN:
                    return PRICE_TO_PLAN[price_id]
    except Exception as e:
        logger.warning(f"Could not resolve plan from subscription {stripe_subscription_id}: {e}")
    return "pro"  # default fallback


def _apply_plan_limits(user_id: str, plan: str):
    """Apply plan limits to tenant."""
    if plan in PLAN_CONFIG:
        cfg = PLAN_CONFIG[plan]
        _db_exec("""
            UPDATE memory_service.tenants
            SET plan = %s, memory_limit = %s, rate_limit_rpm = %s
            WHERE id = (SELECT tenant_id FROM memory_service.profiles WHERE id = %s::UUID)
        """, (plan, cfg["memory_limit"], cfg["rate_limit_rpm"], user_id), fetch=False)
    else:
        _db_exec("""
            UPDATE memory_service.tenants
            SET plan = 'free', memory_limit = %s, rate_limit_rpm = %s
            WHERE id = (SELECT tenant_id FROM memory_service.profiles WHERE id = %s::UUID)
        """, (FREE_LIMITS["memory_limit"], FREE_LIMITS["rate_limit_rpm"], user_id), fetch=False)


def _upsert_subscription(user_id: str, stripe_customer_id: str,
                          stripe_subscription_id: str, plan: str,
                          status: str, period_start=None, period_end=None):
    """Create or update subscription record."""
    existing = _db_exec("""
        SELECT id FROM memory_service.subscriptions
        WHERE user_id = %s::UUID AND stripe_subscription_id = %s
    """, (user_id, stripe_subscription_id))

    if existing:
        _db_exec("""
            UPDATE memory_service.subscriptions
            SET status = %s, plan = %s, current_period_start = %s,
                current_period_end = %s, updated_at = now()
            WHERE user_id = %s::UUID AND stripe_subscription_id = %s
        """, (status, plan, period_start, period_end, user_id, stripe_subscription_id), fetch=False)
    else:
        _db_exec("""
            INSERT INTO memory_service.subscriptions
                (user_id, stripe_customer_id, stripe_subscription_id, plan, status,
                 current_period_start, current_period_end)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s)
        """, (user_id, stripe_customer_id, stripe_subscription_id, plan, status,
              period_start, period_end), fetch=False)

    # Update user plan
    active_plan = plan if status == "active" else "free"
    _db_exec("""
        UPDATE memory_service.profiles SET plan = %s, updated_at = now() WHERE id = %s::UUID
    """, (active_plan, user_id), fetch=False)

    # Apply appropriate limits
    if status == "active":
        _apply_plan_limits(user_id, plan)
    else:
        _apply_plan_limits(user_id, "free")

    logger.info(f"Subscription upserted: user={user_id} sub={stripe_subscription_id} plan={plan} status={status}")


def _find_user_by_stripe_customer(customer_id: str) -> str | None:
    """Find user_id by stripe_customer_id."""
    rows = _db_exec("""
        SELECT id FROM memory_service.profiles WHERE stripe_customer_id = %s
    """, (customer_id,))
    return str(rows[0][0]) if rows else None


# ─── Endpoints ───────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str = "pro"
    interval: str = "monthly"  # "monthly" or "yearly"
    billing: str = ""  # frontend sends "annual" or "monthly" — alias for interval


class CheckoutResponse(BaseModel):
    checkout_url: str


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest = CheckoutRequest(), claims: dict = Depends(require_jwt)):
    """Create a Stripe Checkout Session for Pro or Scale subscription."""
    user_id = claims["sub"]
    plan = body.plan.lower()

    if plan not in PLAN_CONFIG:
        raise HTTPException(400, detail=f"Invalid plan: {plan}. Must be 'pro' or 'scale'.")

    # Accept both "interval" and "billing" field from frontend
    raw_interval = body.billing or body.interval
    interval = "yearly" if raw_interval.lower() in ("yearly", "annual") else "monthly"

    customer_id = _get_or_create_stripe_customer(user_id)
    price_id = PLAN_CONFIG[plan][f"price_id_{interval}"]

    if not price_id:
        raise HTTPException(400, detail=f"No {interval} price configured for {plan} plan.")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{SITE_BASE}/checkout-success.html",
        cancel_url=f"{SITE_BASE}/pricing?checkout=cancelled",
        metadata={"user_id": user_id, "plan": plan},
    )

    logger.info(f"Checkout session created: {session.id} for user {user_id} plan={plan}")
    return CheckoutResponse(checkout_url=session.url)


class SubscriptionResponse(BaseModel):
    has_subscription: bool
    plan: str
    plan_name: str | None = None
    status: str | None = None
    current_period_start: str | None = None
    current_period_end: str | None = None
    stripe_subscription_id: str | None = None


PLAN_DISPLAY_NAMES = {
    "free": "Free",
    "pro": "Pro",
    "scale": "Scale",
}


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(claims: dict = Depends(require_jwt)):
    """Get current user's subscription status."""
    user_id = claims["sub"]
    sub = _get_subscription(user_id)

    if not sub:
        return SubscriptionResponse(has_subscription=False, plan="free", plan_name="Free")

    active_plan = sub["plan"] if sub["status"] == "active" else "free"
    return SubscriptionResponse(
        has_subscription=sub["status"] == "active",
        plan=active_plan,
        plan_name=PLAN_DISPLAY_NAMES.get(active_plan, active_plan.title()),
        status=sub["status"],
        current_period_start=sub["current_period_start"],
        current_period_end=sub["current_period_end"],
        stripe_subscription_id=sub["stripe_subscription_id"],
    )


class PortalResponse(BaseModel):
    portal_url: str


@router.post("/portal", response_model=PortalResponse)
async def create_portal(claims: dict = Depends(require_jwt)):
    """Create a Stripe Customer Portal session for self-service management."""
    user_id = claims["sub"]
    customer_id = _get_or_create_stripe_customer(user_id)

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{SITE_BASE}/dashboard",
    )

    logger.info(f"Portal session created for user {user_id}")
    return PortalResponse(portal_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events. Public endpoint — verifies signature."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(400, detail="Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("Webhook signature verification failed")
        raise HTTPException(400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(400, detail="Webhook error")

    event_type = event["type"]
    # Stripe SDK v15+ returns objects, not dicts — convert for .get() compatibility
    data_obj = event["data"]["object"]
    data = data_obj.to_dict() if hasattr(data_obj, 'to_dict') else data_obj
    logger.info(f"Webhook received: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif event_type == "customer.subscription.created":
            _handle_subscription_change(data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_change(data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif event_type == "invoice.paid":
            _handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data)
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
    except Exception as e:
        logger.error(f"Webhook handler error for {event_type}: {e}")
        pass

    return {"status": "ok"}


# ─── Webhook Handlers ───────────────────────────────────────────────────────

def _handle_checkout_completed(session):
    """Activate subscription after successful checkout."""
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")
    plan = session.get("metadata", {}).get("plan", "pro")

    if not user_id:
        user_id = _find_user_by_stripe_customer(customer_id)

    if not user_id:
        logger.error(f"checkout.session.completed: no user found for customer {customer_id}")
        return

    if subscription_id:
        sub = stripe.Subscription.retrieve(subscription_id)
        period_start = datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc) if sub.current_period_start else None
        period_end = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc) if sub.current_period_end else None

        # Resolve plan from subscription price if not in metadata
        if plan not in PLAN_CONFIG:
            plan = _resolve_plan_from_subscription(subscription_id)

        _upsert_subscription(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            status="active",
            period_start=period_start,
            period_end=period_end,
        )

    logger.info(f"Checkout completed: user={user_id} sub={subscription_id} plan={plan}")


def _handle_subscription_change(subscription):
    """Record new or updated subscription."""
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    status = subscription.get("status", "active")

    user_id = _find_user_by_stripe_customer(customer_id)
    if not user_id:
        logger.error(f"subscription change: no user for customer {customer_id}")
        return

    # Determine plan from price
    plan = _resolve_plan_from_subscription(subscription_id)

    period_start = datetime.fromtimestamp(subscription["current_period_start"], tz=timezone.utc) if subscription.get("current_period_start") else None
    period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=timezone.utc) if subscription.get("current_period_end") else None

    _upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status=status,
        period_start=period_start,
        period_end=period_end,
    )


def _handle_subscription_deleted(subscription):
    """Deactivate subscription."""
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")

    user_id = _find_user_by_stripe_customer(customer_id)
    if not user_id:
        logger.error(f"subscription.deleted: no user for customer {customer_id}")
        return

    plan = _resolve_plan_from_subscription(subscription_id)

    _upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="canceled",
    )
    logger.info(f"Subscription canceled: user={user_id}")


def _handle_invoice_paid(invoice):
    """Extend subscription period on successful payment."""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        return

    user_id = _find_user_by_stripe_customer(customer_id)
    if not user_id:
        return

    sub = stripe.Subscription.retrieve(subscription_id)
    period_start = datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc) if sub.current_period_start else None
    period_end = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc) if sub.current_period_end else None

    plan = _resolve_plan_from_subscription(subscription_id)

    _upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="active",
        period_start=period_start,
        period_end=period_end,
    )
    logger.info(f"Invoice paid, period extended: user={user_id} plan={plan}")


def _handle_payment_failed(invoice):
    """Mark subscription at-risk on failed payment."""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        return

    user_id = _find_user_by_stripe_customer(customer_id)
    if not user_id:
        return

    plan = _resolve_plan_from_subscription(subscription_id)

    _upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
        status="past_due",
    )
    logger.warning(f"Payment failed, subscription at-risk: user={user_id}")
