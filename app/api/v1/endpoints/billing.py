"""Billing and subscription management endpoints."""

from math import ceil
from typing import Annotated
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import get_db

logger = get_logger(__name__)
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.payment_method import PaymentMethod
from app.models.quota import OrganizationQuota
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.billing import (
    BillingUsageResponse,
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    CustomerPortalCreate,
    CustomerPortalResponse,
    InvoiceListResponse,
    InvoiceResponse,
    PaymentMethodCreate,
    PaymentMethodResponse,
    SubscriptionCancelRequest,
    SubscriptionPlanResponse,
    SubscriptionResponse,
    SubscriptionUpgradeRequest,
)
from app.services.billing_service import BillingService
from app.services.stripe_service import StripeService

router = APIRouter(prefix="/billing", tags=["billing"])


# ============================================================================
# Helper Functions
# ============================================================================


async def get_user_organization(
    db: AsyncSession, user: User
) -> Organization:
    """Get the user's primary organization."""
    result = await db.execute(
        select(Organization)
        .join(Organization.members)
        .where(User.id == user.id)
        .limit(1)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return org


async def ensure_organization_owner(org: Organization, user: User) -> None:
    """Ensure user is the organization owner."""
    if org.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can manage billing",
        )


# ============================================================================
# Subscription Plans
# ============================================================================


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def list_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SubscriptionPlan]:
    """List all available subscription plans."""
    return await BillingService.list_active_plans(db)


# ============================================================================
# Subscription Management
# ============================================================================


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Subscription:
    """Get current organization subscription."""
    org = await get_user_organization(db, current_user)

    subscription = await BillingService.get_organization_subscription(db, org.id)

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    return subscription


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    checkout_data: CheckoutSessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout session for subscription.

    User will be redirected to Stripe-hosted checkout page.
    """
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    # Get the plan
    plan = await BillingService.get_plan_by_id(db, checkout_data.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    if plan.is_free:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout for free plan",
        )

    # Get or create Stripe customer
    subscription = await BillingService.get_organization_subscription(db, org.id)

    if not subscription:
        # Create customer if doesn't exist
        customer = await StripeService.create_customer(
            email=current_user.email,
            name=org.name,
            organization_id=str(org.id),
        )
        stripe_customer_id = customer.id

        # Create free subscription to track customer
        subscription = await BillingService.create_free_subscription(
            db, org.id, stripe_customer_id
        )
        await db.commit()
    else:
        stripe_customer_id = subscription.stripe_customer_id

    # Determine price ID based on billing cycle
    if checkout_data.billing_cycle == "yearly":
        stripe_price_id = plan.stripe_price_id  # Would use yearly price ID
    else:
        stripe_price_id = plan.stripe_price_id

    if not stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No Stripe price configured for plan: {plan.name}",
        )

    # Create checkout session
    try:
        session = await StripeService.create_checkout_session(
            customer_id=stripe_customer_id,
            price_id=stripe_price_id,
            success_url=checkout_data.success_url,
            cancel_url=checkout_data.cancel_url,
            trial_period_days=checkout_data.trial_days or settings.BILLING_TRIAL_DAYS,
            metadata={
                "organization_id": str(org.id),
                "plan_id": str(plan.id),
            },
        )

        return CheckoutSessionResponse(
            session_id=session.id,
            session_url=session.url,
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {e!s}",
        )


@router.post("/subscription/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    upgrade_data: SubscriptionUpgradeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Subscription:
    """Upgrade or downgrade subscription plan."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    try:
        subscription = await BillingService.upgrade_subscription(
            db=db,
            organization_id=org.id,
            new_plan_id=upgrade_data.new_plan_id,
            billing_cycle=upgrade_data.billing_cycle,
            prorate=upgrade_data.prorate,
        )
        await db.commit()

        return subscription

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe upgrade error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade subscription: {e!s}",
        )


@router.post("/subscription/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    cancel_data: SubscriptionCancelRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Subscription:
    """Cancel subscription."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    try:
        subscription = await BillingService.cancel_subscription(
            db=db,
            organization_id=org.id,
            immediately=cancel_data.cancel_immediately,
        )

        # Log the cancellation reason if provided
        if cancel_data.reason:
            await BillingService.log_billing_event(
                db=db,
                organization_id=org.id,
                event_type="subscription.cancel_requested",
                event_data={"reason": cancel_data.reason},
                subscription_id=subscription.id,
            )

        await db.commit()

        return subscription

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe cancel error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {e!s}",
        )


@router.post("/subscription/resume", response_model=SubscriptionResponse)
async def resume_subscription(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Subscription:
    """Resume a subscription scheduled for cancellation."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    try:
        subscription = await BillingService.resume_subscription(db, org.id)
        await db.commit()

        return subscription

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe resume error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume subscription: {e!s}",
        )


# ============================================================================
# Payment Methods
# ============================================================================


@router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PaymentMethod]:
    """List all payment methods for the organization."""
    org = await get_user_organization(db, current_user)

    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.organization_id == org.id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    )

    return list(result.scalars().all())


@router.post("/payment-methods", response_model=PaymentMethodResponse)
async def add_payment_method(
    payment_data: PaymentMethodCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaymentMethod:
    """Add a payment method to the organization."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    subscription = await BillingService.get_organization_subscription(db, org.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    try:
        # Attach payment method to customer in Stripe
        stripe_pm = await StripeService.attach_payment_method(
            payment_data.stripe_payment_method_id,
            subscription.stripe_customer_id,
        )

        # Set as default if requested
        if payment_data.set_as_default:
            await StripeService.set_default_payment_method(
                subscription.stripe_customer_id,
                payment_data.stripe_payment_method_id,
            )

            # Unset other default payment methods
            await db.execute(
                select(PaymentMethod)
                .where(PaymentMethod.organization_id == org.id)
                .where(PaymentMethod.is_default)
            )
            existing_defaults = await db.execute(
                select(PaymentMethod)
                .where(PaymentMethod.organization_id == org.id)
                .where(PaymentMethod.is_default)
            )
            for pm in existing_defaults.scalars():
                pm.is_default = False

        # Save to database
        payment_method = await BillingService.save_payment_method(
            db, org.id, stripe_pm, is_default=payment_data.set_as_default
        )
        await db.commit()

        return payment_method

    except stripe.error.StripeError as e:
        logger.error(f"Stripe payment method error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add payment method: {e!s}",
        )


@router.delete("/payment-methods/{payment_method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment_method(
    payment_method_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a payment method."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.organization_id == org.id,
        )
    )
    payment_method = result.scalar_one_or_none()

    if not payment_method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found",
        )

    try:
        # Detach from Stripe
        await StripeService.detach_payment_method(payment_method.stripe_payment_method_id)

        # Delete from database
        await db.delete(payment_method)
        await db.commit()

    except stripe.error.StripeError as e:
        logger.error(f"Stripe detach error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove payment method: {e!s}",
        )


@router.put("/payment-methods/{payment_method_id}/default", response_model=PaymentMethodResponse)
async def set_default_payment_method(
    payment_method_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaymentMethod:
    """Set a payment method as default."""
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.organization_id == org.id,
        )
    )
    payment_method = result.scalar_one_or_none()

    if not payment_method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found",
        )

    subscription = await BillingService.get_organization_subscription(db, org.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    try:
        # Set as default in Stripe
        await StripeService.set_default_payment_method(
            subscription.stripe_customer_id,
            payment_method.stripe_payment_method_id,
        )

        # Unset other defaults
        existing_defaults = await db.execute(
            select(PaymentMethod)
            .where(PaymentMethod.organization_id == org.id)
            .where(PaymentMethod.is_default)
        )
        for pm in existing_defaults.scalars():
            pm.is_default = False

        # Set this as default
        payment_method.is_default = True
        await db.commit()

        return payment_method

    except stripe.error.StripeError as e:
        logger.error(f"Stripe set default error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default payment method: {e!s}",
        )


# ============================================================================
# Invoices
# ============================================================================


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """List invoices for the organization."""
    org = await get_user_organization(db, current_user)

    skip = (page - 1) * page_size

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.organization_id == org.id)
    )
    total = count_result.scalar_one()

    # Get invoices
    result = await db.execute(
        select(Invoice)
        .where(Invoice.organization_id == org.id)
        .order_by(Invoice.created_at.desc())
        .offset(skip)
        .limit(page_size)
    )
    invoices = list(result.scalars().all())

    return InvoiceListResponse(
        items=invoices,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Invoice:
    """Get invoice details."""
    org = await get_user_organization(db, current_user)

    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.organization_id == org.id,
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    return invoice


# ============================================================================
# Customer Portal
# ============================================================================


@router.post("/portal", response_model=CustomerPortalResponse)
async def create_portal_session(
    portal_data: CustomerPortalCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerPortalResponse:
    """
    Create a Stripe Customer Portal session.

    User will be redirected to Stripe-hosted portal where they can:
    - Update payment methods
    - View invoices
    - Manage subscription
    """
    org = await get_user_organization(db, current_user)
    await ensure_organization_owner(org, current_user)

    subscription = await BillingService.get_organization_subscription(db, org.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    try:
        session = await StripeService.create_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=portal_data.return_url,
        )

        return CustomerPortalResponse(portal_url=session.url)

    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {e!s}",
        )


# ============================================================================
# Usage & Billing Period
# ============================================================================


@router.get("/usage", response_model=BillingUsageResponse)
async def get_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> BillingUsageResponse:
    """Get current billing period usage and quota information."""
    org = await get_user_organization(db, current_user)

    subscription = await BillingService.get_organization_subscription(db, org.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    # Get quota
    result = await db.execute(
        select(OrganizationQuota).where(OrganizationQuota.organization_id == org.id)
    )
    quota = result.scalar_one_or_none()

    if not quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quota found",
        )

    # Calculate days remaining
    days_remaining = subscription.days_until_renewal

    return BillingUsageResponse(
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        days_remaining=days_remaining,
        users_count=quota.current_users,
        users_limit=quota.max_users,
        storage_used_bytes=quota.current_storage_bytes,
        storage_limit_bytes=quota.max_storage_bytes,
        api_calls_this_month=quota.current_api_calls_this_month,
        api_calls_limit=quota.max_api_calls_per_month,
        file_uploads_today=quota.current_file_uploads_today,
        file_uploads_limit=quota.max_file_uploads_per_day,
        usage_percentages={
            "users": quota.get_usage_percentage("users"),
            "storage": quota.get_usage_percentage("storage"),
            "api_calls": quota.get_usage_percentage("api_calls"),
            "file_uploads": quota.get_usage_percentage("file_uploads"),
        },
    )
