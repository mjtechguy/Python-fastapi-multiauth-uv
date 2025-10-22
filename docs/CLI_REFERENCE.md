# CLI Quick Reference

Complete command reference for the SaaS Backend CLI tool.

## Installation

```bash
uv pip install -e ".[cli]"
```

## Quick Start

```bash
# 1. Register
python cli.py auth register

# 2. Login (saves token)
python cli.py auth login

# 3. Test API
python cli.py auth me
python cli.py health check-all
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

**With options:**
```bash
python cli.py auth register \
  --email user@example.com \
  --password "SecurePass123!" \
  --name "John Doe"
```

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
- Documents: PDF, DOCX, TXT, CSV
- Images: PNG, JPG, GIF, WEBP
- Archives: ZIP, TAR, GZ
- Any file type (configurable limit: 50MB default)

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
- Connection
- Query performance
- Schema version

#### Redis
```bash
python cli.py health redis
```

Checks:
- Connection
- Read/write operations
- Memory usage

#### Celery
```bash
python cli.py health celery
```

Checks:
- Worker count
- Active tasks
- Registered tasks

#### Storage
```bash
python cli.py health storage
```

Checks:
- Connection
- Upload/download
- Available space

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

### 2. Organization Setup

```bash
# Login
python cli.py auth login

# Create organization
python cli.py org create \
  --name "My Startup" \
  --slug "my-startup"

# Check quota
python cli.py quota status

# List organizations
python cli.py org list
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

### 4. Webhook Setup

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

### 5. System Monitoring

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
