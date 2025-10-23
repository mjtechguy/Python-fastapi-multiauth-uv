# Stripe Integration Setup Guide

This guide will walk you through setting up Stripe payment processing for your SaaS Backend Framework.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Stripe Account Setup](#stripe-account-setup)
3. [Create Products and Prices](#create-products-and-prices)
4. [Configure Environment Variables](#configure-environment-variables)
5. [Database Migration](#database-migration)
6. [Seed Subscription Plans](#seed-subscription-plans)
7. [Configure Webhooks](#configure-webhooks)
8. [Testing](#testing)
9. [Go Live](#go-live)

---

## Prerequisites

Before starting, ensure you have:

- ✅ A Stripe account ([sign up here](https://dashboard.stripe.com/register))
- ✅ Stripe CLI installed for local testing ([installation guide](https://stripe.com/docs/stripe-cli))
- ✅ Application running locally or deployed
- ✅ Database with migrations applied

---

## Stripe Account Setup

### 1. Create a Stripe Account

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Sign up or log in to your account
3. Complete business verification (required for live mode)

### 2. Enable Test Mode

For development, work in **Test Mode** (toggle in the top-right of the dashboard).

### 3. Get API Keys

1. Navigate to **Developers → API keys**
2. Copy your:
   - **Publishable key** (starts with `pk_test_` in test mode)
   - **Secret key** (starts with `sk_test_` in test mode)

⚠️ **Never commit secret keys to version control!**

---

## Create Products and Prices

### Option 1: Via Stripe Dashboard (Recommended)

1. Navigate to **Products** in the Stripe Dashboard
2. Click **Add product** for each plan

#### Free Plan
- Name: `Free`
- Description: `Perfect for getting started`
- **Don't create a price** (free tier doesn't need Stripe price)

#### Starter Plan
- Name: `Starter`
- Description: `For small teams getting serious`
- Pricing:
  - **Monthly**: $29/month
  - Click **Add another price** for yearly
  - **Yearly**: $290/year (save ~17%)
- Copy the **Price ID** for monthly (e.g., `price_1ABC...`)

#### Pro Plan
- Name: `Pro`
- Description: `For growing businesses`
- Pricing:
  - **Monthly**: $99/month
  - **Yearly**: $990/year
- Copy the **Price ID** for monthly

#### Enterprise Plan
- Name: `Enterprise`
- Description: `For large organizations`
- Pricing:
  - **Monthly**: $499/month
  - **Yearly**: $4990/year
- Copy the **Price ID** for monthly

### Option 2: Via Stripe API

```bash
# Create Starter product
stripe products create \
  --name="Starter" \
  --description="For small teams getting serious"

# Create monthly price for Starter
stripe prices create \
  --product=prod_XXX \
  --unit-amount=2900 \
  --currency=usd \
  --recurring[interval]=month

# Create yearly price for Starter
stripe prices create \
  --product=prod_XXX \
  --unit-amount=29000 \
  --currency=usd \
  --recurring[interval]=year
```

---

## Configure Environment Variables

Update your `.env` file with Stripe credentials:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51ABC...
STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...
STRIPE_WEBHOOK_SECRET=whsec_XXX  # Will get this in webhook setup
STRIPE_API_VERSION=2025-09-30

# Stripe Price IDs (from previous step)
STRIPE_PRICE_STARTER_MONTHLY=price_1ABC...
STRIPE_PRICE_STARTER_YEARLY=price_1DEF...
STRIPE_PRICE_PRO_MONTHLY=price_1GHI...
STRIPE_PRICE_PRO_YEARLY=price_1JKL...
STRIPE_PRICE_ENTERPRISE_MONTHLY=price_1MNO...
STRIPE_PRICE_ENTERPRISE_YEARLY=price_1PQR...

# Billing Configuration
BILLING_TRIAL_DAYS=14
BILLING_GRACE_PERIOD_DAYS=3
BILLING_SEND_RECEIPTS=true
BILLING_ALLOW_DOWNGRADES=true
```

### Production Keys

For production, replace with **live mode** keys:
- `sk_live_...` (secret key)
- `pk_live_...` (publishable key)

---

## Database Migration

### 1. Install Dependencies

```bash
# Using uv
uv pip install -e ".[dev]"
```

### 2. Run Migration

The Stripe billing migration was auto-generated. Apply it:

```bash
# Using uv
uv run python -m alembic upgrade head
```

This creates the following tables:
- `subscription_plans` - Plan definitions
- `subscriptions` - Organization subscriptions
- `payment_methods` - Customer payment methods
- `invoices` - Billing invoices
- `billing_events` - Audit log

### 3. Verify Migration

```bash
# Check current migration version
uv run python -m alembic current

# Should show: 9f3c4e4b41de (head)
```

---

## Seed Subscription Plans

Populate the database with default subscription plans:

```bash
# Run seed script
uv run python scripts/seed_subscription_plans.py
```

This creates four plans:
1. **Free** - 3 users, 1GB storage, 1K API calls/month
2. **Starter** - 10 users, 10GB storage, 10K API calls/month
3. **Pro** - 50 users, 100GB storage, 100K API calls/month (Featured)
4. **Enterprise** - Unlimited users, storage, API calls

### Verify Seeding

```bash
# Check plans in database
uv run python -c "
import asyncio
from app.db.session import async_session_maker
from sqlalchemy import select
from app.models.subscription_plan import SubscriptionPlan

async def check():
    async with async_session_maker() as db:
        result = await db.execute(select(SubscriptionPlan))
        plans = result.scalars().all()
        for plan in plans:
            print(f'{plan.name}: {plan.display_name}')

asyncio.run(check())
"
```

---

## Configure Webhooks

Webhooks notify your application of Stripe events (payments, subscriptions, etc.).

### Local Development (Stripe CLI)

1. **Install Stripe CLI** ([guide](https://stripe.com/docs/stripe-cli))

2. **Login to Stripe**
   ```bash
   stripe login
   ```

3. **Forward webhooks to local server**
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```

4. **Copy webhook secret**

   The CLI will print something like:
   ```
   Your webhook signing secret is whsec_abc123...
   ```

   Add to `.env`:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_abc123...
   ```

5. **Restart your application** to load the new secret

### Production (Stripe Dashboard)

1. Navigate to **Developers → Webhooks** in Stripe Dashboard

2. Click **Add endpoint**

3. Configure:
   - **Endpoint URL**: `https://api.yourdomain.com/api/v1/webhooks/stripe`
   - **Description**: Production webhook for SaaS Backend
   - **Events to send**: Select these events:
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `customer.subscription.trial_will_end`
     - `invoice.created`
     - `invoice.finalized`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
     - `payment_method.attached`
     - `payment_method.detached`

4. Click **Add endpoint**

5. Copy the **Signing secret** (starts with `whsec_`)

6. Update production `.env`:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_your_production_secret
   ```

7. Deploy updated environment variables

### Test Webhooks

Trigger a test event:

```bash
# Using Stripe CLI
stripe trigger customer.subscription.created
```

Check your application logs to verify the webhook was processed.

---

## Testing

### 1. Test Card Numbers

Use Stripe's test cards for development:

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 9995` | Declined payment |
| `4000 0000 0000 0341` | Requires 3D Secure |
| `4000 0025 0000 3155` | Requires authentication |

**CVC**: Any 3 digits
**Expiry**: Any future date
**ZIP**: Any 5 digits

### 2. Test Checkout Flow

1. Start your application:
   ```bash
   docker-compose up -d
   ```

2. Create a test organization and user

3. Use API or frontend to create checkout session:
   ```bash
   # Using curl
   curl -X POST http://localhost:8000/api/v1/billing/checkout \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "plan_id": "UUID_OF_STARTER_PLAN",
       "billing_cycle": "monthly",
       "success_url": "http://localhost:3000/success",
       "cancel_url": "http://localhost:3000/cancel"
     }'
   ```

4. Visit the returned `session_url`

5. Complete checkout with test card

6. Verify:
   - Subscription created in database
   - Quotas updated to match plan
   - Webhook events logged

### 3. Test Customer Portal

```bash
curl -X POST http://localhost:8000/api/v1/billing/portal \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "return_url": "http://localhost:3000/settings"
  }'
```

Visit the `portal_url` to test:
- Updating payment methods
- Viewing invoices
- Canceling subscription

### 4. Test Quota Enforcement

Try to exceed quotas and verify proper error messages:

```bash
# Add more users than plan allows
# Upload larger files than plan allows
# Make more API calls than plan allows
```

---

## Go Live

### Production Checklist

Before launching with real payments:

- [ ] **Switch to Live Mode** in Stripe Dashboard
- [ ] **Update API keys** to live keys (`sk_live_`, `pk_live_`)
- [ ] **Create live products/prices** (same as test mode)
- [ ] **Update price IDs** in production `.env`
- [ ] **Configure production webhook** endpoint
- [ ] **Update webhook secret** to production value
- [ ] **Enable required payment methods** (cards, ACH, etc.)
- [ ] **Set up Stripe Tax** (if selling globally)
- [ ] **Configure email notifications** for receipts
- [ ] **Test end-to-end** with small real transaction
- [ ] **Monitor Stripe Dashboard** for first few transactions
- [ ] **Set up alerts** for failed payments
- [ ] **Review terms of service** and privacy policy
- [ ] **Comply with SCA/PSD2** (if in EU)

### Monitoring

Monitor these in Stripe Dashboard:

1. **Payments** - Success/failure rates
2. **Subscriptions** - MRR, churn rate
3. **Customers** - Growth, retention
4. **Radar** - Fraud detection (enable in settings)
5. **Logs** - API requests and webhook events

### Security Best Practices

✅ **Never expose secret keys**
- Use environment variables
- Don't commit to git
- Rotate keys if exposed

✅ **Verify webhook signatures**
- Always validate `stripe-signature` header
- Reject unsigned requests

✅ **Use HTTPS in production**
- Required for PCI compliance
- Protects API keys in transit

✅ **Implement idempotency**
- Webhook events already handled via `stripe_event_id`
- Use idempotency keys for manual API calls

✅ **Handle errors gracefully**
- Retry failed webhook processing
- Send notifications for failed payments
- Provide clear error messages to users

---

## Troubleshooting

### Webhook not receiving events

1. Check webhook URL is publicly accessible
2. Verify `STRIPE_WEBHOOK_SECRET` matches dashboard
3. Check application logs for signature errors
4. Use Stripe CLI to test locally: `stripe listen`

### Subscription not updating quotas

1. Check webhook events are being processed
2. Verify `plan_id` in subscription metadata
3. Check `billing_events` table for errors
4. Review application logs for exceptions

### Payment failing

1. Use test cards from [Stripe docs](https://stripe.com/docs/testing)
2. Check customer has valid payment method
3. Review Radar rules (may block test cards)
4. Check Stripe Dashboard → Logs for API errors

### Database migration issues

```bash
# Reset and reapply migrations
uv run python -m alembic downgrade -1
uv run python -m alembic upgrade head

# Or create new migration
uv run python -m alembic revision --autogenerate -m "fix billing"
```

---

## Additional Resources

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Python Library](https://github.com/stripe/stripe-python)
- [Webhook Best Practices](https://stripe.com/docs/webhooks/best-practices)
- [Testing Stripe](https://stripe.com/docs/testing)
- [PCI Compliance](https://stripe.com/docs/security/guide)
- [SCA/3DS Guide](https://stripe.com/docs/strong-customer-authentication)

---

## Support

- **Stripe Support**: https://support.stripe.com
- **Community**: https://github.com/stripe/stripe-python/discussions
- **Status Page**: https://status.stripe.com

---

**Last Updated:** 2025-10-23
**Version:** 1.0
**Stripe API Version:** 2025-09-30
