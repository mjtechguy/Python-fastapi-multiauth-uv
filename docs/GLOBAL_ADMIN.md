# Global Admin (Superuser) System

## Overview

The Global Admin system (implemented via the `is_superuser` flag) provides system-wide administrative access. Global admins (superusers) have **unrestricted access to all resources and operations** across the entire platform, bypassing all permission checks.

## What is a Global Admin?

A **Global Admin** (also called a **Superuser**) is a user with the `is_superuser = True` flag set on their account. This gives them:

- **Full access to all API endpoints** (no permission checks)
- **Access to all organizations, teams, and resources** (bypasses membership requirements)
- **Ability to manage other users**, including:
  - View all users
  - Grant/revoke superuser status to others
  - Delete users
- **Access to system-wide operations** like health checks, system configuration, etc.

## Key Concepts

### Superuser vs Organization Admin

It's important to distinguish between:

| Feature | Global Admin (Superuser) | Organization Admin |
|---------|-------------------------|-------------------|
| Scope | Entire system | Single organization |
| Access | All resources everywhere | Only org resources |
| Permissions | Bypasses all checks | Subject to RBAC |
| Can manage | All users & orgs | Org members only |
| Flag | `is_superuser = True` | Admin role in org |

**Example**:
- **Global Admin**: Can access/modify any file, any organization, any user across the entire system
- **Org Admin**: Can only manage users and resources within their specific organization

## First User is Automatically a Global Admin

The **first user to register** is automatically granted superuser status. This ensures there's always at least one person with full system access.

**Implementation** (`app/api/v1/endpoints/auth.py:74-83`):
```python
# Check if this is the first user - make them superuser (global admin)
user_count = await db.execute(select(func.count(User.id)))
total_users = user_count.scalar_one()

if total_users == 1:
    # First user becomes superuser (global admin)
    user.is_superuser = True
    await db.flush()
```

**When you register the first user**, they will:
1. ✅ Be automatically granted `is_superuser = True`
2. ✅ Become the owner of the default organization
3. ✅ Have full access to all system operations

## Managing Global Admins

### CLI Commands

#### List all Global Admins
```bash
python cli.py admin list
```

Lists all users with superuser status.

#### Grant Superuser Status
```bash
python cli.py admin grant <user_id>
```

**Example**:
```bash
# First, get the user ID
python cli.py auth login admin@example.com password123

# View all users to find the ID
python cli.py users list

# Grant superuser status
python cli.py admin grant "123e4567-e89b-12d3-a456-426614174000"
```

**Requirements**:
- Only existing superusers can grant superuser status
- Target user must exist and not already be a superuser

#### Revoke Superuser Status
```bash
python cli.py admin revoke <user_id>
```

**Example**:
```bash
python cli.py admin revoke "123e4567-e89b-12d3-a456-426614174000"
```

**Requirements**:
- Only existing superusers can revoke superuser status
- Cannot revoke your own superuser status (safety feature)
- Target user must be a superuser

### API Endpoints

#### Grant Superuser Status
```http
POST /api/v1/users/{user_id}/superuser
Authorization: Bearer <token>
```

**Response**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "username": "newadmin",
  "is_superuser": true,
  "is_active": true,
  "is_verified": true,
  "created_at": "2025-10-22T20:00:00Z"
}
```

**Errors**:
- `403 Forbidden` - Caller is not a superuser
- `404 Not Found` - User doesn't exist
- `400 Bad Request` - User is already a superuser

#### Revoke Superuser Status
```http
DELETE /api/v1/users/{user_id}/superuser
Authorization: Bearer <token>
```

**Response**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "is_superuser": false,
  "...": "..."
}
```

**Errors**:
- `403 Forbidden` - Caller is not a superuser
- `404 Not Found` - User doesn't exist
- `400 Bad Request` - User is not a superuser OR trying to revoke own status

#### List Global Admins
```http
GET /api/v1/users?is_superuser=true
Authorization: Bearer <token>
```

**Response**:
```json
{
  "items": [
    {
      "id": "...",
      "email": "admin@example.com",
      "is_superuser": true,
      "..."
: "..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "pages": 1
}
```

## How Permissions Work for Superusers

The RBAC system automatically grants all permissions to superusers:

**Implementation** (`app/services/rbac.py:184-185`):
```python
# Superusers have all permissions
if user.is_superuser:
    return True
```

This means:
- ✅ Superusers bypass **all** `check_permission()` calls
- ✅ No need to assign roles to superusers
- ✅ Organization/team membership checks don't apply
- ✅ Full CRUD access to all resources

## Typical Use Cases

### 1. Initial System Setup
```bash
# Register first user (becomes superuser automatically)
python cli.py auth register admin@company.com SecurePass123!

# Login
python cli.py auth login admin@company.com SecurePass123!

# Create organizations, configure system
python cli.py org create "Engineering" engineering
python cli.py org create "Marketing" marketing
```

### 2. Adding Another Global Admin
```bash
# Login as existing superuser
python cli.py auth login admin@company.com SecurePass123!

# Register new user (regular user)
python cli.py auth register manager@company.com SecurePass456!

# Get new user's ID
USER_ID=$(python cli.py users list | grep manager@company.com | ...)

# Grant superuser status
python cli.py admin grant "$USER_ID"
```

### 3. Emergency Access to Organization
```bash
# As a superuser, you can access any organization even if not a member
# The system automatically bypasses membership checks for superusers

# View files in any organization
python cli.py files list

# Access any team, any resource
python cli.py teams list <any_org_id>
```

### 4. Removing Admin Access
```bash
# Login as superuser
python cli.py auth login admin@company.com SecurePass123!

# Revoke superuser from another user
python cli.py admin revoke "$USER_ID"

# Note: You cannot revoke your own superuser status
```

## Security Best Practices

### 1. Limit Number of Superusers
- Keep the number of global admins to a minimum (ideally 2-3)
- Only grant superuser status to highly trusted personnel
- Regular users should use organization-level admin roles instead

### 2. Audit Superuser Actions
- Monitor all operations performed by superusers
- Log superuser grants/revokes in audit logs
- Review superuser activity regularly

### 3. Cannot Lock Yourself Out
- The system prevents you from revoking your own superuser status
- Always maintain at least 2 superusers to prevent single point of failure
- Document superuser accounts securely

### 4. Use Organization Admins When Possible
- For organization-specific administration, use organization admin roles
- Reserve global admin for system-wide operations only
- This provides better isolation and reduces risk

## Checking Superuser Status

### Via API
```http
GET /api/v1/users/me
Authorization: Bearer <token>
```

**Response**:
```json
{
  "id": "...",
  "email": "admin@example.com",
  "is_superuser": true,  ← This field indicates superuser status
  "is_active": true,
  "is_verified": true,
  "..."
}
```

### Via CLI
```bash
# View your own profile
python cli.py auth me

# Or list all superusers
python cli.py admin list
```

### In Code
```python
# Check if current user is superuser
if current_user.is_superuser:
    # User has full system access
    pass

# The RBAC service automatically handles this
has_permission = await RBACService.check_permission(
    db, current_user, "organizations", "delete"
)
# Returns True automatically if current_user.is_superuser == True
```

## Database Schema

### User Model
```python
class User(Base):
    # ... other fields ...

    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
```

The `is_superuser` field is:
- **Boolean** (True/False)
- **Defaults to False** for new users
- **Set to True** for first user automatically
- **Can be modified** only by existing superusers

## Troubleshooting

### Problem: No superusers in the system
**Solution**: This shouldn't happen if you followed setup correctly. If it does:
1. Directly modify the database to set a user as superuser
2. Connect to PostgreSQL: `psql -h localhost -U postgres -d saas_db`
3. Run: `UPDATE users SET is_superuser = true WHERE email = 'your-email@example.com';`

### Problem: Cannot grant superuser status
**Errors**:
- `403 Forbidden` → You're not logged in as a superuser
- `404 Not Found` → User ID is incorrect
- `400 Bad Request` → User is already a superuser

**Solution**:
1. Verify you're logged in as a superuser: `python cli.py auth me`
2. Verify the target user exists: `python cli.py users list`
3. Check if user is already a superuser: `python cli.py admin list`

### Problem: Accidentally only one superuser left
**Risk**: If that superuser is locked out, you'll need database access

**Prevention**:
- Always maintain 2+ superusers
- Document superuser credentials securely
- Before revoking superuser, ensure others exist

## Summary

The Global Admin (Superuser) system provides:

✅ **Automatic first-user setup** - No manual configuration needed
✅ **Full system access** - Bypasses all permission checks
✅ **CLI & API management** - Easy to grant/revoke superuser status
✅ **Safety features** - Cannot revoke own status
✅ **Clear distinction** - Different from organization-level admins
✅ **Minimal configuration** - Works out of the box

**Key Commands**:
- `python cli.py auth register` - First user becomes superuser automatically
- `python cli.py admin list` - List all global admins
- `python cli.py admin grant <user_id>` - Grant superuser status
- `python cli.py admin revoke <user_id>` - Revoke superuser status

For most day-to-day operations, use **organization-level admin roles**. Reserve global admin for system-wide tasks and emergency access.
