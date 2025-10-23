"""Pydantic schemas for billing and subscriptions."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Subscription Plan Schemas
# ============================================================================


class SubscriptionPlanBase(BaseModel):
    """Base subscription plan schema."""

    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=255)
    description: str | None = None
    price_monthly: Decimal = Field(default=Decimal("0.00"), ge=0)
    price_yearly: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="usd", max_length=3)
    max_users: int = Field(default=10, ge=-1)
    max_storage_bytes: int = Field(default=1_073_741_824, ge=-1)
    max_api_calls_per_month: int = Field(default=10000, ge=-1)
    max_file_uploads_per_day: int = Field(default=100, ge=-1)
    max_file_size_bytes: int = Field(default=10_485_760, ge=-1)
    features: dict = Field(default_factory=dict)
    tier_level: int = Field(default=0, ge=0)
    is_active: bool = True
    is_featured: bool = False


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Schema for creating a subscription plan."""

    stripe_price_id: str | None = None
    stripe_product_id: str | None = None


class SubscriptionPlanUpdate(BaseModel):
    """Schema for updating a subscription plan."""

    display_name: str | None = None
    description: str | None = None
    price_monthly: Decimal | None = None
    price_yearly: Decimal | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    features: dict | None = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """Schema for subscription plan response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stripe_price_id: str | None
    stripe_product_id: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Subscription Schemas
# ============================================================================


class SubscriptionBase(BaseModel):
    """Base subscription schema."""

    status: Literal[
        "active", "trialing", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired"
    ]
    cancel_at_period_end: bool = False


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""

    plan_id: UUID
    trial_days: int | None = None


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""

    plan_id: UUID | None = None
    cancel_at_period_end: bool | None = None


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    plan_id: UUID
    stripe_subscription_id: str | None
    stripe_customer_id: str
    canceled_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    trial_start: datetime | None
    trial_end: datetime | None
    is_active: bool
    is_trialing: bool
    days_until_renewal: int
    created_at: datetime
    updated_at: datetime

    # Nested plan data
    plan: SubscriptionPlanResponse | None = None


# ============================================================================
# Payment Method Schemas
# ============================================================================


class PaymentMethodBase(BaseModel):
    """Base payment method schema."""

    type: Literal["card", "us_bank_account", "sepa_debit"]


class PaymentMethodCreate(BaseModel):
    """Schema for creating/attaching a payment method."""

    stripe_payment_method_id: str = Field(..., max_length=255)
    set_as_default: bool = False


class PaymentMethodResponse(PaymentMethodBase):
    """Schema for payment method response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    stripe_payment_method_id: str
    display_name: str
    card_brand: str | None
    card_last4: str | None
    card_exp_month: int | None
    card_exp_year: int | None
    bank_name: str | None
    bank_last4: str | None
    is_default: bool
    is_expired: bool
    created_at: datetime


# ============================================================================
# Invoice Schemas
# ============================================================================


class InvoiceBase(BaseModel):
    """Base invoice schema."""

    status: Literal["draft", "open", "paid", "void", "uncollectible"]


class InvoiceResponse(InvoiceBase):
    """Schema for invoice response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    subscription_id: UUID | None
    stripe_invoice_id: str
    invoice_number: str | None
    amount_due: float  # in dollars
    amount_paid: float  # in dollars
    amount_remaining: float  # in dollars
    subtotal: float  # in dollars
    tax: float  # in dollars
    total: float  # in dollars
    currency: str
    invoice_pdf: str | None
    hosted_invoice_url: str | None
    billing_reason: str | None
    period_start: datetime | None
    period_end: datetime | None
    due_date: datetime | None
    paid_at: datetime | None
    is_paid: bool
    is_overdue: bool
    created_at: datetime


class InvoiceListResponse(BaseModel):
    """Schema for paginated invoice list."""

    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================================
# Checkout & Billing Schemas
# ============================================================================


class CheckoutSessionCreate(BaseModel):
    """Schema for creating a Stripe Checkout session."""

    plan_id: UUID
    billing_cycle: Literal["monthly", "yearly"] = "monthly"
    success_url: str = Field(..., max_length=500)
    cancel_url: str = Field(..., max_length=500)
    trial_days: int | None = None


class CheckoutSessionResponse(BaseModel):
    """Schema for Checkout session response."""

    session_id: str
    session_url: str


class CustomerPortalCreate(BaseModel):
    """Schema for creating a Stripe Customer Portal session."""

    return_url: str = Field(..., max_length=500)


class CustomerPortalResponse(BaseModel):
    """Schema for Customer Portal response."""

    portal_url: str


class SubscriptionUpgradeRequest(BaseModel):
    """Schema for upgrading/downgrading subscription."""

    new_plan_id: UUID
    billing_cycle: Literal["monthly", "yearly"] = "monthly"
    prorate: bool = True


class SubscriptionCancelRequest(BaseModel):
    """Schema for canceling subscription."""

    cancel_immediately: bool = False
    reason: str | None = Field(None, max_length=500)


# ============================================================================
# Usage & Quota Schemas
# ============================================================================


class BillingUsageResponse(BaseModel):
    """Schema for billing period usage response."""

    period_start: datetime
    period_end: datetime
    days_remaining: int
    users_count: int
    users_limit: int
    storage_used_bytes: int
    storage_limit_bytes: int
    api_calls_this_month: int
    api_calls_limit: int
    file_uploads_today: int
    file_uploads_limit: int
    usage_percentages: dict[str, float]


# ============================================================================
# Webhook Schemas
# ============================================================================


class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook event."""

    id: str
    type: str
    data: dict
    created: int


# ============================================================================
# Billing Event Schemas
# ============================================================================


class BillingEventResponse(BaseModel):
    """Schema for billing event response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    subscription_id: UUID | None
    event_type: str
    stripe_event_id: str | None
    event_data: dict
    processed: bool
    processed_at: datetime | None
    error_message: str | None
    created_at: datetime


# ============================================================================
# Plan Comparison Schemas
# ============================================================================


class PlanFeatureComparison(BaseModel):
    """Schema for comparing plan features."""

    feature_name: str
    free: bool
    starter: bool
    pro: bool
    enterprise: bool


class PlansComparisonResponse(BaseModel):
    """Schema for all plans comparison."""

    plans: list[SubscriptionPlanResponse]
    feature_comparison: list[PlanFeatureComparison]
