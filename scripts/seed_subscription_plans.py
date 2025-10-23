"""Seed default subscription plans into the database."""

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.subscription_plan import SubscriptionPlan
from app.core.config import settings
from app.core.logging_config import logger


# Default subscription plan configurations
DEFAULT_PLANS = {
    "free": {
        "display_name": "Free",
        "description": "Perfect for getting started and trying out the platform",
        "price_monthly": Decimal("0.00"),
        "price_yearly": Decimal("0.00"),
        "stripe_price_id": None,
        "stripe_product_id": None,
        "max_users": 3,
        "max_storage_bytes": 1_073_741_824,  # 1 GB
        "max_api_calls_per_month": 1000,
        "max_file_uploads_per_day": 10,
        "max_file_size_bytes": 5_242_880,  # 5 MB
        "features": {
            "basic_support": True,
            "custom_domain": False,
            "priority_support": False,
            "sso": False,
            "advanced_analytics": False,
            "api_access": True,
            "webhooks": False,
            "team_collaboration": False,
        },
        "tier_level": 0,
        "is_active": True,
        "is_featured": False,
    },
    "starter": {
        "display_name": "Starter",
        "description": "For small teams getting serious about their work",
        "price_monthly": Decimal("29.00"),
        "price_yearly": Decimal("290.00"),  # ~17% discount
        "stripe_price_id": settings.STRIPE_PRICE_STARTER_MONTHLY or None,
        "stripe_product_id": None,
        "max_users": 10,
        "max_storage_bytes": 10_737_418_240,  # 10 GB
        "max_api_calls_per_month": 10000,
        "max_file_uploads_per_day": 100,
        "max_file_size_bytes": 52_428_800,  # 50 MB
        "features": {
            "basic_support": True,
            "custom_domain": False,
            "priority_support": False,
            "sso": False,
            "advanced_analytics": True,
            "api_access": True,
            "webhooks": True,
            "team_collaboration": True,
        },
        "tier_level": 1,
        "is_active": True,
        "is_featured": False,
    },
    "pro": {
        "display_name": "Pro",
        "description": "For growing businesses that need more power and flexibility",
        "price_monthly": Decimal("99.00"),
        "price_yearly": Decimal("990.00"),  # ~17% discount
        "stripe_price_id": settings.STRIPE_PRICE_PRO_MONTHLY or None,
        "stripe_product_id": None,
        "max_users": 50,
        "max_storage_bytes": 107_374_182_400,  # 100 GB
        "max_api_calls_per_month": 100000,
        "max_file_uploads_per_day": 1000,
        "max_file_size_bytes": 104_857_600,  # 100 MB
        "features": {
            "basic_support": True,
            "custom_domain": True,
            "priority_support": True,
            "sso": False,
            "advanced_analytics": True,
            "api_access": True,
            "webhooks": True,
            "team_collaboration": True,
            "priority_queue": True,
        },
        "tier_level": 2,
        "is_active": True,
        "is_featured": True,  # Featured plan
    },
    "enterprise": {
        "display_name": "Enterprise",
        "description": "For large organizations with advanced needs and compliance requirements",
        "price_monthly": Decimal("499.00"),
        "price_yearly": Decimal("4990.00"),  # ~17% discount
        "stripe_price_id": settings.STRIPE_PRICE_ENTERPRISE_MONTHLY or None,
        "stripe_product_id": None,
        "max_users": -1,  # Unlimited
        "max_storage_bytes": -1,  # Unlimited
        "max_api_calls_per_month": -1,  # Unlimited
        "max_file_uploads_per_day": -1,  # Unlimited
        "max_file_size_bytes": 1_073_741_824,  # 1 GB
        "features": {
            "basic_support": True,
            "custom_domain": True,
            "priority_support": True,
            "sso": True,
            "advanced_analytics": True,
            "api_access": True,
            "webhooks": True,
            "team_collaboration": True,
            "priority_queue": True,
            "dedicated_support": True,
            "custom_integrations": True,
            "sla_guarantee": True,
            "audit_logs": True,
        },
        "tier_level": 3,
        "is_active": True,
        "is_featured": False,
    },
}


async def seed_subscription_plans(db: AsyncSession) -> None:
    """Seed default subscription plans into database."""
    logger.info("Seeding subscription plans...")

    plans_created = 0
    plans_updated = 0

    for plan_name, plan_data in DEFAULT_PLANS.items():
        # Check if plan already exists
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name)
        )
        existing_plan = result.scalar_one_or_none()

        if existing_plan:
            # Update existing plan
            for key, value in plan_data.items():
                setattr(existing_plan, key, value)

            logger.info(f"Updated plan: {plan_name}")
            plans_updated += 1
        else:
            # Create new plan
            new_plan = SubscriptionPlan(
                name=plan_name,
                **plan_data,
            )
            db.add(new_plan)

            logger.info(f"Created plan: {plan_name}")
            plans_created += 1

    await db.commit()

    logger.info(
        f"Subscription plans seeding complete",
        extra={"created": plans_created, "updated": plans_updated},
    )


async def main():
    """Run the seeding script."""
    async with async_session_maker() as db:
        try:
            await seed_subscription_plans(db)
            print("✅ Subscription plans seeded successfully!")

        except Exception as e:
            logger.error(f"Error seeding plans: {str(e)}")
            print(f"❌ Error seeding plans: {str(e)}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
