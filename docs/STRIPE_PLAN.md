# Stripe Payment Integration Plan

## Overview

This document outlines the complete implementation plan for integrating Stripe payment processing into the SaaS Backend Framework. The integration will enable subscription-based billing, payment method management, and automated quota enforcement based on subscription tiers.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Database Schema](#database-schema)
3. [Subscription Plans](#subscription-plans)
4. [API Endpoints](#api-endpoints)
5. [Webhook Events](#webhook-events)
6. [Background Tasks](#background-tasks)
7. [Integration with Quota System](#integration-with-quota-system)
8. [Implementation Phases](#implementation-phases)
9. [Testing Strategy](#testing-strategy)
10. [Security Considerations](#security-considerations)

---

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Billing    │  │    Stripe    │  │   Webhook    │      │
│  │  Endpoints   │  │  Webhooks    │  │   Handler    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────┬───────┴──────────────────┘              │
│                    │                                         │
│         ┌──────────▼──────────┐                             │
│         │  BillingService     │                             │
│         │  - Subscription Mgmt│                             │
│         │  - Quota Integration│                             │
│         └──────────┬──────────┘                             │
│                    │                                         │
│         ┌──────────▼──────────┐                             │
│         │   StripeService     │                             │
│         │  - API Wrapper      │                             │
│         │  - Customer Mgmt    │                             │
│         └──────────┬──────────┘                             │
│                    │                                         │
└────────────────────┼─────────────────────────────────────────┘
                     │
                     ▼
              ┌─────────────┐
              │  Stripe API │
              └─────────────┘
```

### Data Flow

1. **Subscription Creation**
   - User clicks "Upgrade" in frontend
   - Backend creates Stripe Checkout Session
   - User completes payment on Stripe-hosted page
   - Stripe webhook confirms subscription creation
   - Backend updates organization quotas

2. **Webhook Processing**
   - Stripe sends webhook event
   - Webhook endpoint verifies signature
   - Event processed by BillingService
   - Database updated (subscription, quotas)
   - Email notification sent (optional)

3. **Quota Enforcement**
   - API request received
   - Middleware checks subscription status
   - QuotaService validates against plan limits
   - Request allowed/denied based on subscription

---

## Database Schema

### New Tables

#### 1. `subscription_plans`

Defines available subscription tiers and their quotas.

```sql
CREATE TABLE subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,  -- free, starter, pro, enterprise
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    stripe_price_id VARCHAR(255) UNIQUE,  -- NULL for free tier
    stripe_product_id VARCHAR(255),

    -- Pricing
    price_monthly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    price_yearly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'usd',

    -- Quota Limits
    max_users INTEGER NOT NULL DEFAULT 10,
    max_storage_bytes BIGINT NOT NULL DEFAULT 1073741824,  -- 1GB
    max_api_calls_per_month INTEGER NOT NULL DEFAULT 10000,
    max_file_uploads_per_day INTEGER NOT NULL DEFAULT 100,
    max_file_size_bytes BIGINT NOT NULL DEFAULT 10485760,  -- 10MB

    -- Features
    features JSONB DEFAULT '{}',  -- {"custom_domain": true, "priority_support": true}

    -- Ordering & Display
    tier_level INTEGER NOT NULL DEFAULT 0,  -- 0=free, 1=starter, 2=pro, 3=enterprise
    is_active BOOLEAN DEFAULT true,
    is_featured BOOLEAN DEFAULT false,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_subscription_plans_tier ON subscription_plans(tier_level);
CREATE INDEX idx_subscription_plans_active ON subscription_plans(is_active);
```

#### 2. `subscriptions`

Tracks organization subscriptions.

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES subscription_plans(id),

    -- Stripe IDs
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255) NOT NULL,

    -- Status
    status VARCHAR(50) NOT NULL,  -- active, trialing, past_due, canceled, unpaid
    cancel_at_period_end BOOLEAN DEFAULT false,
    canceled_at TIMESTAMP WITH TIME ZONE,

    -- Billing Period
    current_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    current_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    trial_start TIMESTAMP WITH TIME ZONE,
    trial_end TIMESTAMP WITH TIME ZONE,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_org_subscription UNIQUE(organization_id)
);

CREATE INDEX idx_subscriptions_org ON subscriptions(organization_id);
CREATE INDEX idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_subscriptions_customer ON subscriptions(stripe_customer_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_period_end ON subscriptions(current_period_end);
```

#### 3. `payment_methods`

Stores customer payment methods.

```sql
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    stripe_payment_method_id VARCHAR(255) NOT NULL UNIQUE,

    -- Payment Method Details
    type VARCHAR(50) NOT NULL,  -- card, us_bank_account, sepa_debit

    -- Card Details (if type=card)
    card_brand VARCHAR(50),  -- visa, mastercard, amex
    card_last4 VARCHAR(4),
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    card_fingerprint VARCHAR(255),

    -- Bank Account Details (if type=us_bank_account)
    bank_name VARCHAR(255),
    bank_last4 VARCHAR(4),

    -- Status
    is_default BOOLEAN DEFAULT false,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_payment_methods_org ON payment_methods(organization_id);
CREATE INDEX idx_payment_methods_stripe_id ON payment_methods(stripe_payment_method_id);
CREATE INDEX idx_payment_methods_default ON payment_methods(is_default) WHERE is_default = true;
```

#### 4. `invoices`

Tracks billing invoices from Stripe.

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Stripe IDs
    stripe_invoice_id VARCHAR(255) NOT NULL UNIQUE,
    stripe_customer_id VARCHAR(255) NOT NULL,

    -- Invoice Details
    invoice_number VARCHAR(255),
    status VARCHAR(50) NOT NULL,  -- draft, open, paid, void, uncollectible

    -- Amounts (in cents)
    amount_due INTEGER NOT NULL,
    amount_paid INTEGER NOT NULL,
    amount_remaining INTEGER NOT NULL,
    subtotal INTEGER NOT NULL,
    tax INTEGER DEFAULT 0,
    total INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'usd',

    -- URLs
    invoice_pdf VARCHAR(500),
    hosted_invoice_url VARCHAR(500),

    -- Billing
    billing_reason VARCHAR(100),  -- subscription_create, subscription_cycle, manual

    -- Dates
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,
    due_date TIMESTAMP WITH TIME ZONE,
    paid_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_invoices_org ON invoices(organization_id);
CREATE INDEX idx_invoices_subscription ON invoices(subscription_id);
CREATE INDEX idx_invoices_stripe_id ON invoices(stripe_invoice_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_period_end ON invoices(period_end);
```

#### 5. `billing_events`

Audit log for billing-related events.

```sql
CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Event Details
    event_type VARCHAR(100) NOT NULL,  -- subscription.created, payment.succeeded, etc.
    stripe_event_id VARCHAR(255) UNIQUE,

    -- Event Data
    event_data JSONB NOT NULL,

    -- Status
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_billing_events_org ON billing_events(organization_id);
CREATE INDEX idx_billing_events_type ON billing_events(event_type);
CREATE INDEX idx_billing_events_processed ON billing_events(processed);
CREATE INDEX idx_billing_events_stripe_id ON billing_events(stripe_event_id);
```

---

## Subscription Plans

### Default Plan Structure

```python
PLANS = {
    "free": {
        "display_name": "Free",
        "description": "Perfect for getting started",
        "price_monthly": 0,
        "price_yearly": 0,
        "stripe_price_id": None,
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
        },
    },
    "starter": {
        "display_name": "Starter",
        "description": "For small teams getting serious",
        "price_monthly": 29,
        "price_yearly": 290,  # ~17% discount
        "stripe_price_id": "price_starter_monthly",  # Set in Stripe Dashboard
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
        },
    },
    "pro": {
        "display_name": "Pro",
        "description": "For growing businesses",
        "price_monthly": 99,
        "price_yearly": 990,
        "stripe_price_id": "price_pro_monthly",
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
        },
    },
    "enterprise": {
        "display_name": "Enterprise",
        "description": "For large organizations",
        "price_monthly": 499,
        "price_yearly": 4990,
        "stripe_price_id": "price_enterprise_monthly",
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
            "dedicated_support": True,
            "custom_integrations": True,
        },
    },
}
```

---

## API Endpoints

### Billing Management

```
POST   /api/v1/billing/checkout                 Create Stripe Checkout Session
GET    /api/v1/billing/subscription              Get current subscription
POST   /api/v1/billing/subscription/upgrade      Upgrade/change subscription plan
POST   /api/v1/billing/subscription/cancel       Cancel subscription
POST   /api/v1/billing/subscription/resume       Resume canceled subscription
GET    /api/v1/billing/plans                     List available subscription plans
GET    /api/v1/billing/invoices                  List invoices (paginated)
GET    /api/v1/billing/invoices/{id}             Get invoice details
GET    /api/v1/billing/payment-methods           List payment methods
POST   /api/v1/billing/payment-methods           Add payment method
DELETE /api/v1/billing/payment-methods/{id}     Remove payment method
PUT    /api/v1/billing/payment-methods/{id}/default  Set default payment method
POST   /api/v1/billing/portal                    Create customer portal session
GET    /api/v1/billing/usage                     Get current billing period usage
```

### Webhook Endpoint

```
POST   /api/v1/webhooks/stripe                   Handle Stripe webhook events
```

---

## Webhook Events

### Events to Handle

1. **customer.subscription.created**
   - Create subscription record
   - Update organization quotas
   - Send welcome email

2. **customer.subscription.updated**
   - Update subscription status
   - Update quotas if plan changed
   - Handle cancellation scheduling

3. **customer.subscription.deleted**
   - Mark subscription as canceled
   - Downgrade to free tier
   - Send cancellation email

4. **invoice.payment_succeeded**
   - Create/update invoice record
   - Extend subscription period
   - Send receipt email

5. **invoice.payment_failed**
   - Update subscription status to past_due
   - Send payment failed email
   - Trigger retry logic

6. **customer.subscription.trial_will_end**
   - Send trial ending notification (3 days before)

7. **payment_method.attached**
   - Store payment method details

8. **payment_method.detached**
   - Remove payment method from database

---

## Background Tasks

### Celery Tasks

```python
# app/tasks/billing.py

@celery_app.task
def sync_subscription_from_stripe(subscription_id: str)
    """Sync subscription data from Stripe."""

@celery_app.task
def sync_customer_from_stripe(customer_id: str)
    """Sync customer data from Stripe."""

@celery_app.task
def update_organization_quotas(organization_id: str)
    """Update quotas based on current subscription."""

@celery_app.task
def send_billing_notification(org_id: str, event_type: str)
    """Send billing-related email notifications."""

@celery_app.task
def check_trial_expiring()
    """Check for trials ending soon (daily cron)."""

@celery_app.task
def check_payment_failures()
    """Check for failed payments and send reminders."""

@celery_app.task
def report_usage_to_stripe(org_id: str)
    """Report metered usage to Stripe (for usage-based billing)."""
```

### Scheduled Tasks (Celery Beat)

```python
# Daily at 2 AM
schedule.update({
    'check-trial-expiring': {
        'task': 'app.tasks.billing.check_trial_expiring',
        'schedule': crontab(hour=2, minute=0),
    },
    'check-payment-failures': {
        'task': 'app.tasks.billing.check_payment_failures',
        'schedule': crontab(hour=3, minute=0),
    },
})
```

---

## Integration with Quota System

### Modified Quota Enforcement Flow

```python
# Before (current)
if quota.is_user_quota_exceeded():
    raise HTTPException(403, "User quota exceeded")

# After (with Stripe)
subscription = await get_active_subscription(org_id)
if not subscription or subscription.status not in ['active', 'trialing']:
    raise HTTPException(402, "Valid subscription required")

plan = subscription.plan
if plan.max_users != -1 and quota.current_users >= plan.max_users:
    raise HTTPException(403, "User quota exceeded. Please upgrade your plan.")
```

### Quota Service Updates

```python
# app/services/quota.py

async def check_quota_with_subscription(
    db: AsyncSession,
    organization_id: UUID,
    quota_type: str,
    amount: int = 1
) -> tuple[bool, str | None]:
    """
    Check quota with subscription validation.

    Returns:
        (allowed: bool, error_message: str | None)
    """
    subscription = await get_active_subscription(db, organization_id)

    # No subscription = free tier only
    if not subscription:
        plan = await get_plan_by_name(db, "free")
    else:
        plan = subscription.plan

    quota = await get_organization_quota(db, organization_id)

    # Check subscription status
    if subscription and subscription.status == 'past_due':
        return False, "Payment failed. Please update your payment method."

    if subscription and subscription.status == 'canceled':
        return False, "Subscription canceled. Please reactivate to continue."

    # Check quotas based on plan limits
    if quota_type == "users":
        if plan.max_users != -1 and quota.current_users >= plan.max_users:
            return False, f"User limit reached ({plan.max_users}). Upgrade to add more users."

    # ... similar checks for storage, api_calls, file_uploads

    return True, None
```

---

## Implementation Phases

### Phase 1: Foundation (Days 1-2)
- [ ] Add Stripe dependency
- [ ] Create database models
- [ ] Create Alembic migration
- [ ] Add Stripe configuration to settings
- [ ] Update .env.example
- [ ] Create Pydantic schemas

### Phase 2: Core Services (Days 3-4)
- [ ] Implement StripeService
  - Customer CRUD
  - Subscription CRUD
  - Payment method handling
  - Checkout session creation
- [ ] Implement BillingService
  - Subscription management
  - Plan upgrades/downgrades
  - Quota integration

### Phase 3: API Endpoints (Days 5-6)
- [ ] Create billing endpoints
- [ ] Create checkout flow
- [ ] Customer portal integration
- [ ] Invoice retrieval
- [ ] Payment method management

### Phase 4: Webhooks (Day 7)
- [ ] Webhook endpoint with signature verification
- [ ] Event handlers for all subscription events
- [ ] Error handling and retry logic
- [ ] Idempotency handling

### Phase 5: Background Tasks (Day 8)
- [ ] Celery tasks for sync operations
- [ ] Email notifications
- [ ] Scheduled checks (trials, failed payments)

### Phase 6: Integration (Day 9)
- [ ] Integrate with existing quota system
- [ ] Update middleware for subscription checks
- [ ] Seed default subscription plans

### Phase 7: Testing (Days 10-11)
- [ ] Unit tests for services
- [ ] Integration tests with Stripe test mode
- [ ] E2E tests for checkout flow
- [ ] Webhook payload testing

### Phase 8: Documentation (Day 12)
- [ ] API documentation updates
- [ ] Stripe setup guide
- [ ] Subscription management docs
- [ ] Troubleshooting guide

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_stripe_service.py
async def test_create_customer()
async def test_create_subscription()
async def test_cancel_subscription()
async def test_update_payment_method()

# tests/unit/test_billing_service.py
async def test_upgrade_plan()
async def test_downgrade_plan()
async def test_quota_enforcement_with_subscription()
```

### Integration Tests

```python
# tests/integration/test_billing_flow.py
async def test_complete_checkout_flow()
async def test_subscription_upgrade_flow()
async def test_payment_failure_handling()
async def test_cancellation_flow()
```

### Webhook Tests

```python
# tests/integration/test_stripe_webhooks.py
async def test_subscription_created_webhook()
async def test_payment_succeeded_webhook()
async def test_payment_failed_webhook()
async def test_webhook_signature_verification()
async def test_webhook_idempotency()
```

### E2E Tests

```python
# tests/e2e/test_billing.py
async def test_user_upgrades_to_pro()
async def test_user_cancels_subscription()
async def test_quota_enforcement_after_upgrade()
async def test_trial_period_expiration()
```

---

## Security Considerations

### 1. Webhook Signature Verification

Always verify Stripe webhook signatures to prevent spoofing:

```python
def verify_stripe_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
```

### 2. Idempotency

Use Stripe event IDs to prevent duplicate processing:

```python
# Check if event already processed
existing = await db.execute(
    select(BillingEvent).where(BillingEvent.stripe_event_id == event.id)
)
if existing.scalar_one_or_none():
    return {"status": "already_processed"}
```

### 3. PCI Compliance

- Never store raw card numbers
- Use Stripe Elements or Checkout for card collection
- Only store Stripe payment method IDs
- Use customer portal for payment method updates

### 4. Access Control

- Only organization owners can manage billing
- Validate organization membership before billing operations
- Use RBAC for billing endpoint access

### 5. Webhook Endpoint Protection

- Use unpredictable webhook URL path
- Rate limit webhook endpoint
- Log all webhook events for audit

### 6. Environment Separation

- Use Stripe test keys in development
- Separate webhook endpoints for test/production
- Never commit Stripe keys to version control

---

## Environment Variables

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...                    # Secret key (never expose)
STRIPE_PUBLISHABLE_KEY=pk_test_...               # Publishable key (frontend)
STRIPE_WEBHOOK_SECRET=whsec_...                  # Webhook signing secret
STRIPE_API_VERSION=2025-09-30                    # API version

# Stripe Plan IDs (created in Stripe Dashboard)
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_YEARLY=price_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_YEARLY=price_...
STRIPE_PRICE_ENTERPRISE_MONTHLY=price_...
STRIPE_PRICE_ENTERPRISE_YEARLY=price_...

# Billing Configuration
BILLING_TRIAL_DAYS=14                            # Default trial period
BILLING_GRACE_PERIOD_DAYS=3                      # Grace period after payment failure
BILLING_SEND_RECEIPTS=true                       # Send email receipts
BILLING_ALLOW_DOWNGRADES=true                    # Allow plan downgrades
```

---

## Error Handling

### Common Stripe Errors

```python
from stripe.error import (
    CardError,              # Card was declined
    RateLimitError,         # Too many requests
    InvalidRequestError,    # Invalid parameters
    AuthenticationError,    # Invalid API key
    APIConnectionError,     # Network issue
    StripeError,            # Generic error
)

async def handle_stripe_error(e: StripeError) -> HTTPException:
    """Convert Stripe errors to HTTP exceptions."""
    if isinstance(e, CardError):
        return HTTPException(402, f"Card error: {e.user_message}")
    elif isinstance(e, RateLimitError):
        return HTTPException(429, "Too many requests to payment processor")
    elif isinstance(e, InvalidRequestError):
        return HTTPException(400, f"Invalid request: {str(e)}")
    elif isinstance(e, AuthenticationError):
        return HTTPException(500, "Payment processor authentication failed")
    elif isinstance(e, APIConnectionError):
        return HTTPException(503, "Payment processor unavailable")
    else:
        return HTTPException(500, "Payment processing error")
```

---

## Monitoring and Alerts

### Metrics to Track

1. **Subscription Metrics**
   - New subscriptions (daily/monthly)
   - Subscription cancellations
   - Churn rate
   - MRR (Monthly Recurring Revenue)
   - Trial conversion rate

2. **Payment Metrics**
   - Payment success rate
   - Payment failure rate
   - Average payment retry attempts
   - Dunning success rate

3. **Technical Metrics**
   - Webhook processing time
   - Webhook failure rate
   - API call latency to Stripe
   - Quota enforcement accuracy

### Alerts

- Payment failure rate > 5%
- Webhook processing failures
- Subscription sync failures
- Quota miscalculations

---

## Migration Strategy

### For Existing Organizations

```python
async def migrate_existing_organizations():
    """Migrate existing orgs to free plan with subscription."""
    orgs = await get_all_organizations()
    free_plan = await get_plan_by_name("free")

    for org in orgs:
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=org.owner.email,
            name=org.name,
            metadata={"organization_id": str(org.id)}
        )

        # Create free subscription (no payment required)
        subscription = await create_subscription(
            organization_id=org.id,
            plan_id=free_plan.id,
            stripe_customer_id=customer.id,
            status="active"
        )

        # Update quotas to match free plan
        await update_organization_quotas(org.id, free_plan)
```

---

## Success Criteria

- [ ] Users can upgrade/downgrade plans via Stripe Checkout
- [ ] Webhooks update subscriptions and quotas automatically
- [ ] Quota enforcement respects subscription limits
- [ ] Payment failures trigger appropriate notifications
- [ ] Customer portal allows self-service billing management
- [ ] All Stripe operations are idempotent
- [ ] Webhook signature verification prevents spoofing
- [ ] Test coverage > 80% for billing code
- [ ] Documentation complete and accurate
- [ ] Production monitoring and alerts configured

---

## Resources

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Python Library](https://github.com/stripe/stripe-python)
- [Stripe Webhook Guide](https://stripe.com/docs/webhooks)
- [Stripe Checkout](https://stripe.com/docs/payments/checkout)
- [Stripe Customer Portal](https://stripe.com/docs/billing/subscriptions/integrating-customer-portal)
- [Stripe Testing](https://stripe.com/docs/testing)

---

**Last Updated:** 2025-10-22
**Version:** 1.0
**Status:** Implementation Ready
