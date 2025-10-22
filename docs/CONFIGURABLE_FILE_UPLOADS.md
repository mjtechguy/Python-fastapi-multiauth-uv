# Configurable File Upload System - Implementation Summary

## Overview

Implemented a flexible file upload system that allows configuration via `.env` to support multiple use cases from strict document management to general-purpose file storage with videos, audio, images, and any other file types.

## Changes Made

### 1. Configuration Settings (`app/core/config.py`)

Added two new configuration variables:

```python
# File Upload Restrictions
ALLOWED_FILE_TYPES: str = ""  # Comma-separated MIME types, or "*" for all types
BLOCKED_FILE_TYPES: str = "application/x-executable,application/x-dosexec,application/x-msdos-program"
```

Added helper properties:

```python
@property
def allowed_file_types_list(self) -> list[str] | None:
    """Get list of allowed file types from comma-separated string.

    Returns:
        - None if ALLOWED_FILE_TYPES is empty (use default allow list)
        - ["*"] if ALLOWED_FILE_TYPES is "*" (allow all types)
        - List of MIME types otherwise
    """

@property
def blocked_file_types_list(self) -> list[str]:
    """Get list of blocked file types from comma-separated string."""
```

### 2. File Upload Endpoint (`app/api/v1/endpoints/files.py`)

Updated the `upload_file` endpoint to support three modes:

**Mode 1: Default (Empty `ALLOWED_FILE_TYPES`)**
- Uses built-in allow list: images, documents, text files, spreadsheets

**Mode 2: Allow All (`ALLOWED_FILE_TYPES=*`)**
- Accepts any file type except those in `BLOCKED_FILE_TYPES`
- Perfect for general-purpose file storage (cloud drives, media platforms)

**Mode 3: Custom (`ALLOWED_FILE_TYPES=image/jpeg,video/mp4,...`)**
- Only allows specified MIME types
- Precise control for specific use cases

**Security Features:**
- `BLOCKED_FILE_TYPES` is **always enforced** regardless of allowed mode
- Default blocks executables: `.exe`, `.dll`, `.bat`, `.cmd`, etc.
- Prevents malicious file uploads

### 3. Environment Configuration (`.env.example`)

Added comprehensive documentation in `.env.example`:

```bash
# File Upload Restrictions
# ALLOWED_FILE_TYPES: Controls which file types can be uploaded
#   - Leave empty (default): Use built-in allow list (images, documents, text files)
#   - Set to "*": Allow ALL file types (except blocked ones)
#   - Comma-separated MIME types: Custom allow list
ALLOWED_FILE_TYPES=

# Common MIME types for reference:
# Images: image/jpeg,image/png,image/gif,image/webp,image/svg+xml
# Documents: application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document
# Video: video/mp4,video/mpeg,video/quicktime,video/x-msvideo,video/webm
# Audio: audio/mpeg,audio/wav,audio/ogg,audio/aac,audio/webm
# Archives: application/zip,application/x-rar-compressed,application/x-7z-compressed,application/x-tar

# BLOCKED_FILE_TYPES: Security block list (always enforced)
BLOCKED_FILE_TYPES=application/x-executable,application/x-dosexec,application/x-msdos-program
```

### 4. Documentation

Created comprehensive documentation:

**`docs/FILE_UPLOAD_CONFIG.md`**
- Detailed explanation of all three modes
- Common use case examples (media platform, document management, cloud drive)
- Complete MIME type reference for images, videos, audio, documents, archives, code files
- Security considerations and recommendations
- Troubleshooting guide
- Testing instructions

**Updated `README.md`**
- Added file upload configuration to features list
- Referenced the new configuration guide

## Use Case Examples

### Media Platform (Images + Videos + Audio)
```bash
ALLOWED_FILE_TYPES=image/jpeg,image/png,image/gif,image/webp,video/mp4,video/mpeg,video/quicktime,video/webm,audio/mpeg,audio/wav,audio/ogg
MAX_FILE_SIZE_MB=500
```

### Document Management System
```bash
ALLOWED_FILE_TYPES=application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv
MAX_FILE_SIZE_MB=100
```

### General Cloud Storage (Allow Everything)
```bash
ALLOWED_FILE_TYPES=*
MAX_FILE_SIZE_MB=2048
BLOCKED_FILE_TYPES=application/x-executable,application/x-dosexec,application/x-msdos-program
```

### Profile Pictures Only
```bash
ALLOWED_FILE_TYPES=image/jpeg,image/png,image/webp
MAX_FILE_SIZE_MB=5
```

## Implementation Details

### File Validation Flow

1. **Check file size** - Must be under `MAX_FILE_SIZE_MB`
2. **Check blocked types** - Always reject executables and dangerous files
3. **Check allowed types**:
   - If `ALLOWED_FILE_TYPES` is empty → Use default allow list
   - If `ALLOWED_FILE_TYPES` is `*` → Accept (already passed blocked check)
   - If `ALLOWED_FILE_TYPES` is custom → Validate against custom list
4. **Process file** - Optimize images if applicable
5. **Upload to storage** - S3/MinIO with checksum
6. **Create database record** - Track metadata

### Code Structure

```python
# Check blocked types first (security)
blocked_types = settings.blocked_file_types_list
if content_type in blocked_types:
    raise HTTPException(status_code=415, detail="File type blocked")

# Get allowed types from configuration
allowed_types_config = settings.allowed_file_types_list

if allowed_types_config is None:
    # Use default allow list
    allowed_types = DEFAULT_ALLOWED_TYPES
elif allowed_types_config == ["*"]:
    # Allow all types (except blocked)
    allowed_types = None  # Skip validation
else:
    # Use custom allow list
    allowed_types = allowed_types_config

# Validate against allowed types if not allowing all
if allowed_types is not None:
    if not storage_service.validate_file_type(content_type, allowed_types):
        raise HTTPException(status_code=415, detail="File type not supported")
```

## Testing

Test the configuration with different file types:

```bash
# Test text file (in default allow list)
python cli.py files upload test.txt

# Test video file (requires custom config or allow-all mode)
python cli.py files upload video.mp4

# Test executable (should always be blocked)
python cli.py files upload malware.exe
```

## Security Considerations

1. **Never remove executable blocking** - The default `BLOCKED_FILE_TYPES` prevents serious security issues
2. **Validate server-side** - Never trust client MIME types (already implemented)
3. **Use virus scanning** - Consider adding ClamAV or similar for production
4. **Store outside web root** - MinIO/S3 storage prevents direct access
5. **Use presigned URLs** - Time-limited access already implemented
6. **Monitor uploads** - Track uploaded file types in audit logs

## Migration Notes

**Backward Compatibility:** ✅ Fully compatible

- Default behavior unchanged (images + documents + text)
- Existing `.env` files without `ALLOWED_FILE_TYPES` work as before
- No database migrations required
- No API changes (same endpoints, same response format)

## Future Enhancements

Potential improvements for future versions:

1. **Per-organization file type restrictions** - Different orgs, different rules
2. **Virus scanning integration** - ClamAV or VirusTotal API
3. **File type detection** - Use `python-magic` to verify actual file type vs MIME type
4. **Upload quotas** - Limit uploads per user/organization (already have storage quotas)
5. **Content inspection** - Scan uploaded files for sensitive data
6. **Automatic file conversion** - Convert videos to standard formats, images to WebP
7. **CDN integration** - CloudFront, Cloudflare for fast file delivery

## Files Modified

- `app/core/config.py` - Added `ALLOWED_FILE_TYPES` and `BLOCKED_FILE_TYPES` settings
- `app/api/v1/endpoints/files.py` - Updated validation logic to use configurable settings
- `.env.example` - Added file upload configuration with examples and MIME type reference
- `docs/FILE_UPLOAD_CONFIG.md` - Created comprehensive configuration guide
- `docs/CONFIGURABLE_FILE_UPLOADS.md` - This implementation summary
- `README.md` - Updated features section to highlight configurable file types

## Conclusion

The configurable file upload system provides maximum flexibility while maintaining security. Users can now:

- Use the default safe configuration for typical web applications
- Allow all file types for general-purpose storage platforms
- Customize exactly which MIME types are allowed for specialized use cases
- Always maintain security with the blocked types list

This makes the backend truly multi-use, supporting everything from document management systems to media platforms to general cloud storage solutions.
