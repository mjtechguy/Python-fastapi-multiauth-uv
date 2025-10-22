# Single Organization Membership

## Overview

Regular users can only be members of **one organization at a time**. This simplifies resource management, billing, and access control.

**Exception**: Global admins (superusers) can be members of multiple organizations for administrative purposes.

## Why Single Organization Membership?

### Benefits

1. **Clear Resource Ownership**
   - Files, teams, and other resources belong to one organization
   - No ambiguity about which organization a user represents
   - Simplified billing and quota management

2. **Simplified Access Control**
   - Users have a single organizational context
   - No confusion about which organization they're acting on behalf of
   - Clearer audit trails and activity logs

3. **Better User Experience**
   - Users don't need to "switch" between organizations
   - Current organization context is always clear
   - Reduces cognitive load

4. **Easier Administration**
   - Org admins know exactly who belongs to their organization
   - No shared users between competing organizations
   - Clearer organizational boundaries

## How It Works

### For Regular Users

When you add a user to an organization:

```bash
python cli.py org add-member "$ORG_ID" --user-id "$USER_ID"
```

**Behavior depends on the user's current organization:**

1. **User in Default Organization**: Automatically moved to the new organization ✅
   ```
   User moved from "Default Organization" to "Your Company"
   ```

2. **User in Another Organization**: Error - must explicitly remove first ❌
   ```
   Error: User is already a member of another organization (Acme Corp).
   Regular users can only belong to one organization at a time.
   Remove them from their current organization first, or grant them superuser status.
   ```

This design makes onboarding smooth (users can easily leave the default org) while preventing accidental moves between real organizations.

### For Global Admins (Superusers)

Global admins can be members of multiple organizations:

```bash
# Grant superuser status
python cli.py admin grant "$USER_ID"

# Now they can be added to multiple organizations
python cli.py org add-member "$ORG1_ID" --user-id "$USER_ID"
python cli.py org add-member "$ORG2_ID" --user-id "$USER_ID"
# Both succeed!
```

## Common Scenarios

### Scenario 1: Onboarding a New User to Your Organization

**Problem**: New user registered and is in the default organization, you want them in your org

**Solution**: Just add them! They'll be automatically moved.
```bash
# User just registered and is in "Default Organization"
python cli.py auth register newuser@example.com password 'New User'

# As your org admin, simply add them
python cli.py org add-member "$YOUR_ORG_ID" --user-id "$NEW_USER_ID"
# ✅ User automatically moved from default org to your org
```

### Scenario 2: Moving a User Between Non-Default Organizations

**Problem**: User needs to switch from "Company A" to "Company B"

**Solution**: Explicit two-step process to prevent accidents
```bash
# 1. Login as admin of Company A
python cli.py auth login admin-a@companya.com password

# 2. Remove user from Company A
python cli.py org remove-member "$COMPANY_A_ID" --user-id "$USER_ID"

# 3. Login as admin of Company B
python cli.py auth login admin-b@companyb.com password

# 4. Add user to Company B
python cli.py org add-member "$COMPANY_B_ID" --user-id "$USER_ID"
```

### Scenario 3: Contractor Working for Multiple Companies

**Problem**: Freelance contractor needs access to multiple client organizations

**Option A - Grant Superuser Status** (for trusted contractors):
```bash
# Global admin grants superuser status
python cli.py admin grant "$CONTRACTOR_ID"

# Now contractor can be in multiple orgs
python cli.py org add-member "$CLIENT1_ID" --user-id "$CONTRACTOR_ID"
python cli.py org add-member "$CLIENT2_ID" --user-id "$CONTRACTOR_ID"
```

**Option B - Use Separate Accounts** (recommended for most cases):
```bash
# Contractor creates separate account for each client
python cli.py auth register contractor+client1@email.com password1
python cli.py auth register contractor+client2@email.com password2

# Each account belongs to one organization
```

### Scenario 4: Internal User Needs Multi-Org Access

**Problem**: Support staff or internal admin needs access to all organizations

**Solution**: Grant them global admin status
```bash
python cli.py admin grant "$SUPPORT_USER_ID"
```

This gives them:
- ✅ Access to all organizations (even if not explicitly a member)
- ✅ Ability to be member of multiple organizations
- ✅ Full system access for administrative tasks

### Scenario 5: User Accidentally Added to Wrong Org

**Problem**: User was added to wrong organization during onboarding

**Solution**: Remove and re-add to correct organization
```bash
# Remove from wrong org
python cli.py org remove-member "$WRONG_ORG_ID" --user-id "$USER_ID"

# Add to correct org
python cli.py org add-member "$CORRECT_ORG_ID" --user-id "$USER_ID"
```

## Default Organization

All users are automatically added to the **Default Organization** when they register:

```bash
# Register new user
python cli.py auth register newuser@example.com password 'New User'
# User is automatically added to "Default Organization"
```

**Moving users from default org is automatic:**
```bash
# Simply add them to your organization
python cli.py org add-member "$YOUR_ORG_ID" --user-id "$USER_ID"
# ✅ User is automatically removed from default org and added to your org
```

No need to explicitly remove them from the default organization first!

## API Behavior

### POST /api/v1/organizations/{org_id}/members

**Success Response** (200):
```json
{
  "message": "Member added successfully"
}
```

**Error: User Already in Another Org** (400):
```json
{
  "detail": "User is already a member of another organization. Regular users can only belong to one organization at a time. Remove them from their current organization first, or grant them superuser status."
}
```

**Error: User Not Found** (400):
```json
{
  "detail": "User not found"
}
```

## Global Admin Exception

Global admins (superusers) are exempt from the single-org rule because:

1. **Administrative Oversight**: They need to manage multiple organizations
2. **Support & Troubleshooting**: Access all orgs for support purposes
3. **System Maintenance**: Perform system-wide operations
4. **Trusted Users**: Only granted to highly trusted personnel

To check if a user is a superuser:
```bash
python cli.py admin list
```

## Database Schema

The relationship is defined in the `user_organizations` association table:

```python
# In app/models/user.py
user_organizations = Table(
    "user_organizations",
    Base.metadata,
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE")),
    Column("organization_id", UUID, ForeignKey("organizations.id", ondelete="CASCADE")),
    Column("created_at", DateTime(timezone=True), default=now)
)
```

**Note**: There's no unique constraint on `user_id` because superusers can be in multiple orgs. The constraint is enforced in application logic.

## Implementation Details

The check happens in `OrganizationService.add_member()`:

```python
# Check if user is a superuser
if not user.is_superuser:
    # Check for existing org membership
    existing_orgs = await db.execute(
        select(user_organizations).where(user_organizations.c.user_id == user_id)
    )
    existing = existing_orgs.first()

    if existing and existing.organization_id != org_id:
        raise ValueError(
            "User is already a member of another organization. "
            "Regular users can only belong to one organization at a time."
        )
```

## Best Practices

### For Organization Owners

1. **Verify before adding**: Check user's current org before adding them
2. **Communicate with users**: Let them know they'll need to leave their current org
3. **Coordinate with other admins**: If moving a user between orgs

### For Global Admins

1. **Limit superuser grants**: Only give to truly trusted personnel
2. **Document superusers**: Keep track of who has multi-org access
3. **Regular audits**: Review superuser list periodically

### For Users

1. **Know your organization**: Understand which org you belong to
2. **Request transfers properly**: Ask admins to move you if needed
3. **Separate accounts for clients**: If contractor, use different emails

## Troubleshooting

### Problem: Can't add user to organization

**Error**: "User is already a member of another organization"

**Solutions**:
1. Check current organization: Where is the user currently?
2. Remove from current org first
3. Or grant superuser status if appropriate

### Problem: Need user in multiple orgs

**Solutions**:
1. Grant superuser status (for trusted users)
2. Create separate user accounts (recommended)
3. Re-think your organization structure

### Problem: Lost track of which org user is in

**Solution**: Query the database or check via API
```bash
# As superuser, list all orgs and their members
python cli.py org list
python cli.py org list-members "$ORG_ID"
```

## Summary

- ✅ Regular users: **1 organization only**
- ✅ Global admins: **Multiple organizations allowed**
- ✅ Clear error messages when violations occur
- ✅ Easy to move users between organizations
- ✅ Default organization for all new users
- ✅ Exceptions for administrative use cases

This design keeps organizations cleanly separated while allowing flexibility for administrative users who need cross-organization access.
