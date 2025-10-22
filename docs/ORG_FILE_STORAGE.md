# Organization-Based File Storage - Implementation Summary

## Overview

Implemented hierarchical file storage organization where files are stored in a structure based on organization and user. All users are automatically added to a default organization, ensuring consistent file organization across the entire system.

## Changes Made

### 1. Default Organization System

**Purpose**: Ensure all users belong to at least one organization for consistent file storage.

#### Created `OrganizationService.get_or_create_default()` (`app/services/organization.py`)

```python
DEFAULT_ORG_NAME = "Default Organization"
DEFAULT_ORG_SLUG = "default"

@staticmethod
async def get_or_create_default(db: AsyncSession) -> Organization:
    """Get or create the default organization.

    The default organization is used when users are not explicitly added to an organization.
    It's automatically created on first use.
    """
```

**Features**:
- Creates a default organization with slug "default" on first use
- First user becomes the owner of the default organization
- All subsequent users are automatically added as members
- Used when no specific organization is provided for file uploads

#### Updated User Registration (`app/api/v1/endpoints/auth.py`)

```python
# Add user to default organization
default_org = await OrganizationService.get_or_create_default(db)

# Set owner_id if this is the first user
if default_org.owner_id is None:
    default_org.owner_id = user.id

# Add user as member
await OrganizationService.add_member(db, default_org.id, user.id)
```

**Behavior**:
- Every new user is automatically added to the default organization
- First user becomes owner of the default organization
- No user is left without an organization

### 2. Hierarchical File Storage Paths

**Purpose**: Organize uploaded files by organization and user for better multi-tenancy isolation.

#### Updated Storage Services (`app/services/storage.py`)

**Path Structure**:
```
uploads/
  └── org_<organization_id>/
      └── user_<user_id>/
          └── <subdirectory>/
              └── <unique_filename>
```

**Example Paths**:
- S3: `uploads/org_123e4567/user_789abcdef/a1/a1b2c3d4-file.pdf`
- Local: `uploads/org_123e4567/user_789abcdef/a1/a1b2c3d4-file.pdf`

**Implementation**:

```python
# Updated method signatures to accept org_id and user_id
async def upload(
    self,
    file: BinaryIO,
    filename: str,
    content_type: str,
    org_id: str | None = None,
    user_id: str | None = None
) -> Tuple[str, str]:
```

**S3StorageService**:
```python
# Build path: uploads/org_<org_id>/user_<user_id>/filename
path_parts = ["uploads"]
if org_id:
    path_parts.append(f"org_{org_id}")
if user_id:
    path_parts.append(f"user_{user_id}")
path_parts.append(unique_filename)

s3_key = "/".join(path_parts)
```

**LocalStorageService**:
```python
# Build path with additional subdirectory for better organization
path_parts = []
if org_id:
    path_parts.append(f"org_{org_id}")
if user_id:
    path_parts.append(f"user_{user_id}")

# Add subdirectory based on first 2 chars of UUID
path_parts.append(unique_filename[:2])

upload_dir = self.base_path / Path(*path_parts)
upload_dir.mkdir(parents=True, exist_ok=True)
```

### 3. File Model Update

**Purpose**: Track which organization a file belongs to.

#### Added `organization_id` Field (`app/models/file.py`)

```python
# Owner and organization
uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
)
organization_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
)
```

**Benefits**:
- Query files by organization
- Enforce organization-based access control
- Track file ownership at org level
- Support organization quotas for file storage

### 4. File Upload Endpoint Updates

**Purpose**: Support organization context for file uploads.

#### Updated Upload Endpoint (`app/api/v1/endpoints/files.py`)

**New Parameter**:
```python
organization_id: UUID | None = Query(None, description="Optional organization ID to store file under")
```

**Behavior**:
1. **If `organization_id` provided**:
   - Verify user is member of the organization
   - Use that organization for file storage

2. **If `organization_id` NOT provided**:
   - Automatically use user's default organization
   - Ensures all files are organized under an organization

**Implementation**:
```python
# Determine organization: use provided one or user's default org
if organization_id:
    # Verify organization membership
    is_member = await OrganizationService.is_member(db, organization_id, current_user.id)
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member")
    final_org_id = organization_id
else:
    # Use user's default organization
    default_org = await OrganizationService.get_or_create_default(db)
    final_org_id = default_org.id

# Upload with org/user path
storage_path, provider, checksum = await storage_service.upload(
    file_obj,
    filename,
    content_type,
    org_id=str(final_org_id),
    user_id=str(current_user.id),
)
```

### 5. CLI Updates

**Purpose**: Support organization-specific file uploads from command line.

#### Updated Upload Command (`cli.py`)

**New Option**:
```bash
--org-id, -o    Organization ID to store file under
```

**Usage Examples**:

```bash
# Upload to default organization (automatic)
python cli.py files upload document.pdf

# Upload to specific organization
python cli.py files upload document.pdf --org-id "123e4567-e89b-12d3-a456-426614174000"

# Short form
python cli.py files upload document.pdf -o "$ORG_ID"
```

**Implementation**:
```python
params = {}
if organization_id:
    params["organization_id"] = organization_id
response = client.post("/api/v1/files/upload", files=files, params=params)
```

## File Organization Benefits

### 1. Multi-Tenancy Isolation
- Files from different organizations are physically separated in storage
- Easy to implement org-level access controls
- Simple to backup/restore/delete all files for an organization

### 2. User-Level Organization
- Each user's files are in their own subdirectory
- Easy to track per-user storage usage
- Simplifies user deletion and data export

### 3. Scalability
- Hierarchical structure prevents too many files in one directory
- UUID-based subdirectories for local storage provide additional distribution
- Works efficiently with millions of files

### 4. Security
- Organization membership verified before file upload
- Files inherit organization-level permissions
- Prevents unauthorized cross-organization file access

### 5. Quota Management
- Easy to calculate storage used by organization
- Can enforce per-organization storage limits
- Per-user quotas within organizations

## File Path Examples

### Example 1: User in Default Organization
**User**: John (user_id: `789abc...`)
**Organization**: Default (org_id: `default123...`)
**File**: `profile.jpg`
**Path**: `uploads/org_default123.../user_789abc.../a1/a1b2c3d4-5678-profile.jpg`

### Example 2: User in Custom Organization
**User**: Jane (user_id: `456def...`)
**Organization**: Acme Corp (org_id: `acme789...`)
**File**: `report.pdf`
**Path**: `uploads/org_acme789.../user_456def.../b2/b2c3d4e5-6789-report.pdf`

### Example 3: Same User in Different Orgs
**User**: Bob (user_id: `123xyz...`)
**Organization 1**: Default
**File 1**: `personal.txt`
**Path 1**: `uploads/org_default123.../user_123xyz.../c3/c3d4e5f6-personal.txt`

**Organization 2**: Company X
**File 2**: `work.docx`
**Path 2**: `uploads/org_companyx.../user_123xyz.../d4/d4e5f6g7-work.docx`

## Database Schema Updates

### Files Table

```sql
ALTER TABLE files
ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX idx_files_organization_id ON files(organization_id);
```

**Migration Required**: Yes, add `organization_id` column to existing `files` table.

## API Changes

### File Upload Endpoint

**Before**:
```http
POST /api/v1/files/upload
Content-Type: multipart/form-data

file=@document.pdf
```

**After (with organization)**:
```http
POST /api/v1/files/upload?organization_id=123e4567-e89b-12d3-a456-426614174000
Content-Type: multipart/form-data

file=@document.pdf
```

**After (uses default organization)**:
```http
POST /api/v1/files/upload
Content-Type: multipart/form-data

file=@document.pdf
```

**Response** (now includes `organization_id`):
```json
{
  "id": "a1b2c3d4-5678-...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size": 1048576,
  "storage_path": "uploads/org_123.../user_789.../a1/a1b2c3d4-document.pdf",
  "organization_id": "123e4567-e89b-12d3-a456-426614174000",
  "uploaded_by_id": "789abcdef-...",
  "created_at": "2025-10-22T21:00:00Z"
}
```

## Backward Compatibility

**Breaking Changes**: ⚠️ Requires migration

### Required Actions:

1. **Database Migration**:
   ```bash
   alembic revision --autogenerate -m "Add organization_id to files table"
   alembic upgrade head
   ```

2. **Existing Files**:
   - Old files without `organization_id` will have `NULL` value
   - Consider migration script to assign existing files to default org or user's primary org

3. **API Behavior**:
   - File upload now ALWAYS stores under an organization (default if none specified)
   - No change to API request format (organization_id is optional parameter)
   - Response includes new `organization_id` field

## Testing

### Test Default Organization Creation

```bash
# Register a new user - should auto-create default org and add user
python cli.py auth register newemail@example.com newpassword123

# Verify default org exists
python cli.py org list
# Should show "Default Organization" with slug "default"
```

### Test File Upload to Default Organization

```bash
# Login
python cli.py auth login youruser@example.com yourpassword

# Upload without specifying org (uses default)
python cli.py files upload test.txt

# Verify file storage path includes org and user
# Check MinIO console or local uploads/ directory
```

### Test File Upload to Specific Organization

```bash
# Create custom organization
python cli.py org create "My Company" mycompany

# Get organization ID
ORG_ID=$(python cli.py org list | grep mycompany | ...)

# Upload to specific org
python cli.py files upload report.pdf --org-id "$ORG_ID"

# Verify file stored under correct org path
```

## Future Enhancements

1. **Organization Storage Quotas**:
   - Track total storage used per organization
   - Enforce max storage limits
   - Send alerts when approaching limits

2. **Shared Files**:
   - Allow files to be shared across organizations
   - Implement file permissions (read/write/admin)
   - Track file shares and access logs

3. **File Migration Tools**:
   - CLI command to move user's files between organizations
   - Bulk organization file operations
   - Storage optimization tools

4. **Analytics**:
   - Storage usage reports per organization
   - File type distribution
   - Most active users/organizations

5. **Cleanup Tasks**:
   - Celery task to clean up orphaned files
   - Archive old files to cold storage
   - Delete files from deleted organizations

## Files Modified

- `app/services/storage.py` - Added org/user path support to S3 and Local storage
- `app/services/organization.py` - Added `get_or_create_default()` method
- `app/models/file.py` - Added `organization_id` foreign key
- `app/api/v1/endpoints/files.py` - Added organization context to upload
- `app/api/v1/endpoints/auth.py` - Auto-add new users to default organization
- `cli.py` - Added `--org-id` option to file upload command
- `docs/ORG_FILE_STORAGE.md` - This implementation summary

## Conclusion

The organization-based file storage system provides:
- ✅ Automatic organization membership for all users via default organization
- ✅ Hierarchical file organization: organization → user → file
- ✅ Multi-tenancy isolation at the storage level
- ✅ Flexible file uploads (specify org or use default)
- ✅ Foundation for organization-level quotas and permissions
- ✅ Scalable structure for millions of files
- ✅ CLI support for organization-specific uploads

All users now have a home organization, and all files are organized in a logical hierarchy that supports multi-tenancy, quotas, and access control.
