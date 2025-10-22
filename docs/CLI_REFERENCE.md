# CLI Quick Reference

Complete command reference for the SaaS Backend CLI tool.

## Installation

```bash
uv pip install -e ".[cli]"
```

## Quick Start

```bash
# 1. Register (first user becomes global admin automatically!)
python cli.py auth register

# 2. Login (saves token)
python cli.py auth login

# 3. Test API
python cli.py auth me
python cli.py health check-all
```

**Note**: The first user you register automatically becomes a **Global Admin (superuser)** with full system access!

## Complete End-to-End Workflow

Here's a complete walkthrough of creating and managing an organization with teams:

```bash
# 1. Register and Login (first user becomes global admin automatically!)
python cli.py auth register --email admin@company.com --password 'SecurePass123!' --name "Admin User"

python cli.py auth login --email admin@company.com --password 'SecurePass123!'

# 2. Create Organization
python cli.py org create \
  --name "My Company" \
  --slug "my-company" \
  --description "Our awesome company"

# Save organization ID from response (e.g., 550e8400-e29b-41d4-a716-446655440000)
ORG_ID="<copy-from-response>"

# 3. Create Teams
python cli.py teams create \
  --name "Engineering" \
  --slug "engineering" \
  --org-id "$ORG_ID" \
  --description "Software development team"

# Save team ID from response
TEAM_ID="<copy-from-response>"

python cli.py teams create \
  --name "Marketing" \
  --slug "marketing" \
  --org-id "$ORG_ID"

# 4. List Your Teams
python cli.py teams list --org-id "$ORG_ID"

# 5. Register Another User (for testing member management)
# Note: The user ID is in the response, save it for next steps
python cli.py auth logout
python cli.py auth register --email developer@company.com --password 'SecurePass123!' --name "Developer User"

# Get the new user ID from the response above
USER_ID="<copy-the-id-from-response>"

# 6. Login Back as Admin
python cli.py auth login --email admin@company.com --password 'SecurePass123!'

# 7. Add User to Organization FIRST (required before adding to team)
python cli.py org add-member "$ORG_ID" \
  --user-id "$USER_ID" \
  --role "member"

# Verify organization membership
python cli.py org list-members "$ORG_ID"

# 8. Add Member to Team (user must be in org first!)
python cli.py teams add-member "$TEAM_ID" \
  --user-id "$USER_ID"

# 9. List Team Members
python cli.py teams list-members "$TEAM_ID"

# 10. Upload Files
python cli.py files upload test.txt
python cli.py files list

# 11. Setup Webhooks
python cli.py webhooks events
python cli.py webhooks create \
  --url-endpoint "https://webhook.site/your-id" \
  --events "user.created,team.created,file.uploaded"

# 12. Check System Health
python cli.py health check-all

# 13. Monitor Usage
python cli.py quota status
python cli.py sessions stats

# 14. Cleanup (Testing)
# Remove from team first
python cli.py teams remove-member "$TEAM_ID" --user-id "$USER_ID"
# Then remove from organization
python cli.py org remove-member "$ORG_ID" --user-id "$USER_ID"
# Delete team
python cli.py teams delete "$TEAM_ID" --yes

# 15. Logout
python cli.py auth logout
```

---

## Authentication Commands

### Register New User

```bash
python cli.py auth register
```

**Interactive prompts:**
- Email
- Password (hidden)
- Full name

**With options (single line - recommended):**
```bash
python cli.py auth register --email user@example.com --password 'SecurePass123!' --name "John Doe"
```

**ZSH users**: Use single quotes `'` around passwords with special characters like `!` to prevent history expansion.

**Bash users**: Can use double quotes `"` but single quotes `'` also work.

**Multi-line format (paste all lines at once):**
```bash
python cli.py auth register \
  --email user@example.com \
  --password 'SecurePass123!' \
  --name "John Doe"
```
Note: The `\` allows line continuation. Paste all lines together or type on one line.

### Login

```bash
python cli.py auth login
```

**Interactive prompts:**
- Email
- Password (hidden)

**With options:**
```bash
python cli.py auth login \
  --email user@example.com \
  --password "SecurePass123!"
```

**Token saved to:** `~/.saas_cli_tokens.json`

### Get Current User

```bash
python cli.py auth me
```

Shows current user profile (requires login).

### Refresh Token

```bash
python cli.py auth refresh
```

Refreshes expired access token using refresh token.

### Logout

```bash
python cli.py auth logout
```

Clears saved tokens.

---

## Admin Commands (Global Admin / Superuser Management)

**Note**: Only superusers can use these commands. The first registered user automatically becomes a superuser.

### List All Global Admins

```bash
python cli.py admin list
```

Shows all users with superuser (global admin) status.

### Grant Global Admin Status

```bash
python cli.py admin grant <user_id>
```

**Example:**
```bash
# First, get the user ID you want to promote
python cli.py auth login admin@example.com password

# View all users (superuser only)
# Use API or get user ID from registration

# Grant superuser status
python cli.py admin grant "123e4567-e89b-12d3-a456-426614174000"
```

**Requirements:**
- Caller must be a superuser
- Target user must exist and not already be a superuser

### Revoke Global Admin Status

```bash
python cli.py admin revoke <user_id>
```

**Example:**
```bash
python cli.py admin revoke "123e4567-e89b-12d3-a456-426614174000"
```

**Requirements:**
- Caller must be a superuser
- Cannot revoke your own superuser status (safety feature)
- Target user must currently be a superuser

**See also:** [Global Admin Documentation](GLOBAL_ADMIN.md) for detailed information about the superuser system.

---

## Organization Commands

### Create Organization

```bash
python cli.py org create
```

**Interactive prompts:**
- Name
- Slug
- Description (optional)

**With options:**
```bash
python cli.py org create \
  --name "My Company" \
  --slug "my-company" \
  --description "My awesome company"
```

### List Organizations

```bash
python cli.py org list
```

Lists all organizations user belongs to.

### Get Organization

```bash
python cli.py org get <org-id>
```

Get details of specific organization.

**Example:**
```bash
python cli.py org get 550e8400-e29b-41d4-a716-446655440000
```

### Add Member to Organization

```bash
python cli.py org add-member <org-id>
```

**Interactive prompt:**
- User ID

**With options:**
```bash
python cli.py org add-member <org-id> \
  --user-id "770e8400-e29b-41d4-a716-446655440000" \
  --role "member"
```

**Roles:**
- `owner` - Full control over organization
- `admin` - Manage members and settings
- `member` - Regular member access (default)

**⚠️ Important:** Users must be added to the organization **before** they can be added to any teams within that organization.

### Remove Member from Organization

```bash
python cli.py org remove-member <org-id>
```

**Interactive prompt:**
- User ID

**With options:**
```bash
python cli.py org remove-member <org-id> \
  --user-id "770e8400-e29b-41d4-a716-446655440000"
```

**Note:** Removing a user from an organization will also remove them from all teams in that organization.

### List Organization Members

```bash
python cli.py org list-members <org-id>
```

Shows all organization members with:
- User ID
- Email
- Full name
- Role (owner, admin, member)
- Join date

**Example:**
```bash
python cli.py org list-members 550e8400-e29b-41d4-a716-446655440000
```

---

## Team Commands

### Create Team

```bash
python cli.py teams create
```

**Interactive prompts:**
- Name
- Slug
- Organization ID
- Description (optional)

**With options:**
```bash
python cli.py teams create \
  --name "Engineering Team" \
  --slug "engineering-team" \
  --org-id "550e8400-e29b-41d4-a716-446655440000" \
  --description "Software development team"
```

### List Teams

```bash
# List all teams user belongs to
python cli.py teams list

# List teams in specific organization
python cli.py teams list --org-id "550e8400-e29b-41d4-a716-446655440000"
```

### Get Team

```bash
python cli.py teams get <team-id>
```

Shows team details including:
- Team name and slug
- Organization
- Member count
- Description
- Created/updated timestamps

**Example:**
```bash
python cli.py teams get 660e8400-e29b-41d4-a716-446655440000
```

### Update Team

```bash
python cli.py teams update <team-id>
```

**Options:**
```bash
# Update name
python cli.py teams update <team-id> --name "New Team Name"

# Update description
python cli.py teams update <team-id> --description "Updated description"

# Update both
python cli.py teams update <team-id> \
  --name "New Name" \
  --description "New description"
```

### Delete Team

```bash
# Interactive confirmation
python cli.py teams delete <team-id>

# Skip confirmation
python cli.py teams delete <team-id> --yes
```

**Warning:** This will permanently delete the team and remove all member associations.

### Add Member to Team

```bash
python cli.py teams add-member <team-id>
```

**Interactive prompt:**
- User ID

**With options:**
```bash
python cli.py teams add-member <team-id> \
  --user-id "770e8400-e29b-41d4-a716-446655440000"
```

**Requirements:**
- User must be a member of the team's organization
- User cannot already be in the team

### Remove Member from Team

```bash
python cli.py teams remove-member <team-id>
```

**Interactive prompt:**
- User ID

**With options:**
```bash
python cli.py teams remove-member <team-id> \
  --user-id "770e8400-e29b-41d4-a716-446655440000"
```

### List Team Members

```bash
python cli.py teams list-members <team-id>
```

Shows all team members with:
- User ID
- Email
- Full name
- Role in organization

---

## File Commands

### Upload File

```bash
python cli.py files upload <file-path>
```

**Examples:**
```bash
python cli.py files upload document.pdf
python cli.py files upload ~/Downloads/image.png
python cli.py files upload ./data/report.xlsx
```

**Supported formats:**
- **Documents:** PDF, DOCX, DOC, XLSX, XLS, TXT, CSV, JSON, Markdown
- **Images:** PNG, JPG/JPEG, GIF, WEBP
- **File size limit:** 50MB (configurable via `MAX_FILE_SIZE_MB` in `.env`)

### List Files

```bash
python cli.py files list
```

Lists all files uploaded by current user.

---

## Session Commands

### List Sessions

```bash
python cli.py sessions list
```

Shows all active sessions with:
- Device information
- IP address
- Login time
- Last activity

### Session Statistics

```bash
python cli.py sessions stats
```

Shows session statistics:
- Total sessions
- Active sessions
- Sessions by device

---

## Webhook Commands

### List Available Events

```bash
python cli.py webhooks events
```

Shows all available webhook event types:
- `user.created`
- `user.updated`
- `user.deleted`
- `file.uploaded`
- `file.deleted`
- `organization.created`
- And more...

### Create Webhook

```bash
python cli.py webhooks create
```

**Interactive prompts:**
- URL endpoint
- Events (comma-separated)
- Description (optional)

**With options:**
```bash
python cli.py webhooks create \
  --url-endpoint "https://webhook.site/your-unique-id" \
  --events "user.created,file.uploaded,organization.updated" \
  --description "Production webhook"
```

### List Webhooks

```bash
python cli.py webhooks list
```

Shows all configured webhooks with:
- URL
- Events
- Status (active/inactive)
- Delivery statistics

---

## Quota Commands

### Get Quota Status

```bash
python cli.py quota status
```

Shows current usage and limits:
- **Users:** 5/10 (50%)
- **Storage:** 2.5GB/10GB (25%)
- **API Calls:** 8,500/10,000 per month (85%)
- **File Uploads:** 45/100 per day (45%)

### Get Usage Logs

```bash
python cli.py quota logs
```

**With pagination:**
```bash
python cli.py quota logs --page 2 --size 50
```

Shows detailed usage history:
- Timestamp
- Usage type
- Amount
- User

---

## Health Check Commands

### Check All Services

```bash
python cli.py health check-all
```

Comprehensive health check of:
- ✅ Database
- ✅ Redis
- ✅ Celery Workers
- ✅ Storage Service

### Check Individual Services

#### Database
```bash
python cli.py health database
```

Checks:
- Connection status
- Query performance (response time in ms)
- Schema version (current Alembic migration)
- Connection pool statistics (size, active connections, overflow)

#### Redis
```bash
python cli.py health redis
```

Checks:
- Connection status
- Read/write operations (with performance metrics)
- Memory usage (used memory, peak memory, fragmentation ratio)
- Redis version and total keys

#### Celery
```bash
python cli.py health celery
```

Checks:
- Worker count and names
- Active tasks (currently running)
- Registered tasks (available task types)
- Worker availability

#### Storage
```bash
python cli.py health storage
```

Checks:
- Connection status
- Upload/download operations (with performance metrics)
- Available space (total, used, available for local storage)
- Storage provider type (S3, local, etc.)

---

## Dead Letter Queue Commands

### DLQ Statistics

```bash
python cli.py dlq stats
```

Shows:
- Total failed tasks
- By status (failed, retrying, resolved, ignored)
- Recent failures (last 24h)

### List Failed Tasks

```bash
python cli.py dlq list
```

**With status filter:**
```bash
python cli.py dlq list --status failed
python cli.py dlq list --status retrying
python cli.py dlq list --status resolved
```

---

## Global Options

### Custom Base URL

```bash
# For single command
python cli.py --url http://localhost:8000 auth login

# Or set environment variable
export API_BASE_URL=http://localhost:8000
python cli.py auth login
```

### Help

```bash
# General help
python cli.py --help

# Command help
python cli.py auth --help
python cli.py auth login --help

# Subcommand help
python cli.py webhooks create --help
```

---

## Output Formatting

The CLI provides rich, colorful output:

### Success (Green ✓)
```
✓ Success: User registered successfully!
```

### Error (Red ✗)
```
✗ Error: Invalid credentials
```

### Status Codes
- **200-299:** 🟢 Green (success)
- **400-499:** 🟡 Yellow (client error)
- **500-599:** 🔴 Red (server error)

### JSON Output

Responses are syntax-highlighted JSON:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Common Workflows

### 1. Complete Registration Flow

```bash
# Register
python cli.py auth register \
  --email user@example.com \
  --password "SecurePass123!" \
  --name "John Doe"

# Login
python cli.py auth login \
  --email user@example.com \
  --password "SecurePass123!"

# Verify
python cli.py auth me
```

### 2. Organization & Team Setup

```bash
# Login
python cli.py auth login

# Create organization
python cli.py org create \
  --name "My Startup" \
  --slug "my-startup"

# Save the organization ID from response
ORG_ID="550e8400-e29b-41d4-a716-446655440000"

# Create teams
python cli.py teams create \
  --name "Engineering" \
  --slug "engineering" \
  --org-id "$ORG_ID"

python cli.py teams create \
  --name "Marketing" \
  --slug "marketing" \
  --org-id "$ORG_ID"

# List teams in organization
python cli.py teams list --org-id "$ORG_ID"

# Check quota
python cli.py quota status
```

### 3. File Management

```bash
# Upload multiple files
python cli.py files upload document1.pdf
python cli.py files upload image1.png
python cli.py files upload data.csv

# List all files
python cli.py files list

# Check storage quota
python cli.py quota status
```

### 4. Team Member Management

```bash
# Save IDs from previous commands
ORG_ID="550e8400-e29b-41d4-a716-446655440000"
TEAM_ID="660e8400-e29b-41d4-a716-446655440000"
USER_ID="770e8400-e29b-41d4-a716-446655440000"

# Add member to team
python cli.py teams add-member "$TEAM_ID" \
  --user-id "$USER_ID"

# List team members
python cli.py teams list-members "$TEAM_ID"

# Get team details (shows member count)
python cli.py teams get "$TEAM_ID"

# Update team information
python cli.py teams update "$TEAM_ID" \
  --description "Updated team description"

# Remove member from team
python cli.py teams remove-member "$TEAM_ID" \
  --user-id "$USER_ID"

# Delete team (with confirmation)
python cli.py teams delete "$TEAM_ID"
```

### 5. Webhook Setup

```bash
# See available events
python cli.py webhooks events

# Create webhook
python cli.py webhooks create \
  --url-endpoint "https://webhook.site/xxx" \
  --events "user.created,file.uploaded"

# Verify webhook created
python cli.py webhooks list
```

### 6. System Monitoring

```bash
# Check all services
python cli.py health check-all

# Check DLQ
python cli.py dlq stats

# Check quotas
python cli.py quota status

# Check sessions
python cli.py sessions stats
```

---

## Environment Variables

```bash
# API base URL (default: http://localhost:8000)
export API_BASE_URL=http://staging.example.com

# Token file location (default: ~/.saas_cli_tokens.json)
export TOKEN_FILE=/custom/path/tokens.json
```

---

## Troubleshooting

### Connection Issues

```bash
# Check API is running
curl http://localhost:8000/health

# Check base URL
echo $API_BASE_URL

# Use explicit URL
python cli.py --url http://localhost:8000 health check-all
```

### Authentication Issues

```bash
# Clear tokens
python cli.py auth logout

# Remove token file
rm ~/.saas_cli_tokens.json

# Login again
python cli.py auth login
```

### Debug Mode

```bash
# Enable detailed output (add to cli.py if needed)
DEBUG=1 python cli.py auth login
```

---

## Tips & Tricks

### 1. Create Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias saas="python /path/to/cli.py"

# Usage
saas auth login
saas health check-all
```

### 2. Shell Completion

```bash
# Generate completion (if using typer)
python cli.py --install-completion

# Or manually add to shell config
_SAAS_COMPLETE=bash_source python cli.py > ~/.saas-complete.bash
source ~/.saas-complete.bash
```

### 3. Pipe Output

```bash
# Save response to file
python cli.py auth me > user_info.json

# Parse with jq
python cli.py auth me | jq '.email'

# Count items
python cli.py files list | jq '.items | length'
```

### 4. Batch Operations

```bash
# Upload multiple files
for file in *.pdf; do
  python cli.py files upload "$file"
done

# Create multiple webhooks
while IFS=, read url events; do
  python cli.py webhooks create --url-endpoint "$url" --events "$events"
done < webhooks.csv
```

---

## API Reference

Full API documentation: **http://localhost:8000/docs**

**Interactive Swagger UI** with all endpoints, schemas, and authentication.

---

## Support

- **Documentation:** [TESTING.md](TESTING.md)
- **API Docs:** http://localhost:8000/docs
- **GitHub Issues:** [Create Issue](https://github.com/yourusername/saas-backend/issues)
