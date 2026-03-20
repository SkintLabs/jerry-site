"""
Jerry The Customer Service Bot — Stripe Billing Service
Handles subscription creation and metered usage reporting.
Currency: USD. Uses Stripe Python SDK (sync calls wrapped in run_in_executor).
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("jerry.billing")

# Only import stripe at module level — it may not be installed yet
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("stripe package not installed — billing disabled")


PLAN_CONFIG = {
    "base": {
        "flat_price_id": os.getenv("STRIPE_BASE_FLAT_PRICE_ID", "price_placeholder_base_flat"),
        "resolution_price_id": os.getenv("STRIPE_BASE_RESOLUTION_PRICE_ID", "price_placeholder_base_res"),
        "revenue_share_price_id": os.getenv("STRIPE_BASE_REVENUE_SHARE_PRICE_ID", "price_placeholder_base_rev"),
        "per_resolution_usd": 50,           # $0.50
        "revenue_share_pct": Decimal("0.02"),  # 2%
    },
    "elite": {
        "flat_price_id": os.getenv("STRIPE_ELITE_FLAT_PRICE_ID", "price_placeholder_elite_flat"),
        "resolution_price_id": os.getenv("STRIPE_ELITE_RESOLUTION_PRICE_ID", "price_placeholder_elite_res"),
        "revenue_share_price_id": os.getenv("STRIPE_ELITE_REVENUE_SHARE_PRICE_ID", "price_placeholder_elite_rev"),
        "per_resolution_usd": 100,          # $1.00
        "revenue_share_pct": Decimal("0.05"),  # 5%
    },
}


class BillingService:
    """Manages Stripe subscriptions and metered usage for Jerry merchants."""

    def __init__(self):
        self.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.configured = bool(self.api_key) and STRIPE_AVAILABLE

        if self.configured:
            stripe.api_key = self.api_key
            logger.info("BillingService initialized (Stripe connected)")
        else:
            logger.warning("BillingService: Stripe not configured — billing disabled")

    async def create_customer(self, store) -> Optional[str]:
        """Create a Stripe customer for a store. Returns customer ID or None."""
        if not self.configured:
            logger.warning("Stripe not configured — skipping customer creation")
            return None

        loop = asyncio.get_running_loop()
        try:
            customer = await loop.run_in_executor(
                None,
                lambda: stripe.Customer.create(
                    email=store.email or "",
                    name=store.name or store.shopify_domain,
                    metadata={
                        "shopify_domain": store.shopify_domain,
                        "store_id": str(store.id),
                    },
                ),
            )
            logger.info(f"Stripe customer created: {customer.id} for {store.shopify_domain}")
            return customer.id
        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            return None

    async def create_subscription(self, customer_id: str, plan: str) -> Optional[dict]:
        """
        Create a hybrid subscription with flat fee + 2 metered price components.
        Returns subscription dict or None.
        """
        if not self.configured:
            return None

        config = PLAN_CONFIG.get(plan)
        if not config:
            logger.error(f"Unknown plan: {plan}")
            return None

        loop = asyncio.get_running_loop()
        try:
            subscription = await loop.run_in_executor(
                None,
                lambda: stripe.Subscription.create(
                    customer=customer_id,
                    items=[
                        {"price": config["flat_price_id"]},
                        {"price": config["resolution_price_id"]},
                        {"price": config["revenue_share_price_id"]},
                    ],
                    currency="usd",
                    payment_behavior="default_incomplete",
                    expand=["latest_invoice.payment_intent"],
                ),
            )
            logger.info(f"Subscription created: {subscription.id} (plan={plan})")
            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret
                if subscription.latest_invoice and subscription.latest_invoice.payment_intent
                else None,
                "status": subscription.status,
            }
        except Exception as e:
            logger.error(f"Failed to create subscription: {e}")
            return None

    async def report_resolution(self, subscription_id: str, plan: str, count: int = 1) -> bool:
        """Push resolution usage to Stripe metered billing."""
        if not self.configured or not subscription_id:
            return False

        config = PLAN_CONFIG.get(plan, PLAN_CONFIG["base"])
        loop = asyncio.get_running_loop()

        try:
            # Find the resolution subscription item
            sub = await loop.run_in_executor(
                None,
                lambda: stripe.Subscription.retrieve(subscription_id),
            )
            res_item = None
            for item in sub["items"]["data"]:
                if item["price"]["id"] == config["resolution_price_id"]:
                    res_item = item
                    break

            if not res_item:
                logger.warning(f"Resolution price item not found in subscription {subscription_id}")
                return False

            await loop.run_in_executor(
                None,
                lambda: stripe.SubscriptionItem.create_usage_record(
                    res_item["id"],
                    quantity=count,
                    action="increment",
                ),
            )
            logger.info(f"Reported {count} resolution(s) to Stripe for sub={subscription_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to report resolution usage: {e}")
            return False

    async def report_revenue_share(self, subscription_id: str, plan: str, order_value_cents: int) -> bool:
        """Calculate commission in USD cents and push to Stripe metered billing."""
        if not self.configured or not subscription_id:
            return False

        config = PLAN_CONFIG.get(plan, PLAN_CONFIG["base"])
        commission_cents = int(order_value_cents * config["revenue_share_pct"])

        if commission_cents <= 0:
            return True  # No commission to report

        loop = asyncio.get_running_loop()

        try:
            sub = await loop.run_in_executor(
                None,
                lambda: stripe.Subscription.retrieve(subscription_id),
            )
            rev_item = None
            for item in sub["items"]["data"]:
                if item["price"]["id"] == config["revenue_share_price_id"]:
                    rev_item = item
                    break

            if not rev_item:
                logger.warning(f"Revenue share price item not found in subscription {subscription_id}")
                return False

            await loop.run_in_executor(
                None,
                lambda: stripe.SubscriptionItem.create_usage_record(
                    rev_item["id"],
                    quantity=commission_cents,
                    action="increment",
                ),
            )
            logger.info(
                f"Reported revenue share: {commission_cents} cents "
                f"({float(config['revenue_share_pct'])*100}% of {order_value_cents}c) "
                f"for sub={subscription_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to report revenue share: {e}")
            return False

    async def handle_webhook_event(self, payload: bytes, sig_header: str) -> Optional[dict]:
        """
        Verify and process a Stripe webhook event.
        Returns the event dict or None if verification fails.
        """
        if not self.configured:
            return None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret,
            )
        except stripe.error.SignatureVerificationError:
            logger.warning("Stripe webhook signature verification failed")
            return None
        except Exception as e:
            logger.error(f"Stripe webhook error: {e}")
            return None

        logger.info(f"Stripe webhook: {event['type']}")
        return event
