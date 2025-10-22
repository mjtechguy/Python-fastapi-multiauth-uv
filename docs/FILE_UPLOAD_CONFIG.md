# File Upload Configuration

This document explains how to configure file upload restrictions for your multi-use backend.

## Overview

The file upload system supports flexible configuration to handle different use cases:
- **Media applications**: Allow images, videos, and audio files
- **Document management**: Allow PDFs, Office documents, and text files
- **General purpose**: Allow all file types with security restrictions
- **Restricted systems**: Allow only specific MIME types

## Configuration Options

### Environment Variables

Configure file uploads using these `.env` variables:

#### `ALLOWED_FILE_TYPES`

Controls which file types can be uploaded. Three modes are supported:

**1. Default Mode (Empty String)**
```bash
ALLOWED_FILE_TYPES=
```
Uses the built-in allow list:
- Images: JPEG, PNG, GIF, WebP
- Documents: PDF, Word, Excel, PowerPoint
- Text: Plain text, CSV, Markdown, JSON

**2. Allow All Mode (Wildcard)**
```bash
ALLOWED_FILE_TYPES=*
```
Allows **all file types** except those in the blocked list. Use this for general-purpose file storage where users may upload any type of content.

**3. Custom Mode (Comma-Separated MIME Types)**
```bash
ALLOWED_FILE_TYPES=image/jpeg,image/png,video/mp4,audio/mpeg
```
Allows only the specified MIME types. Use this when you need precise control over allowed file types.

#### `BLOCKED_FILE_TYPES`

Security block list that is **always enforced** regardless of `ALLOWED_FILE_TYPES` setting.

Default value blocks executables:
```bash
BLOCKED_FILE_TYPES=application/x-executable,application/x-dosexec,application/x-msdos-program
```

You can add additional dangerous file types if needed:
```bash
BLOCKED_FILE_TYPES=application/x-executable,application/x-dosexec,application/x-msdos-program,application/x-sh,application/x-python-code
```

#### `MAX_FILE_SIZE_MB`

Maximum file size in megabytes (default: 50MB):
```bash
MAX_FILE_SIZE_MB=100
```

## Common Use Cases

### Media Platform (Images, Videos, Audio)
```bash
ALLOWED_FILE_TYPES=image/jpeg,image/png,image/gif,image/webp,video/mp4,video/mpeg,video/quicktime,video/webm,audio/mpeg,audio/wav,audio/ogg,audio/aac
MAX_FILE_SIZE_MB=500
```

### Document Management System
```bash
ALLOWED_FILE_TYPES=application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/csv
MAX_FILE_SIZE_MB=100
```

### General File Storage (Cloud Drive)
```bash
ALLOWED_FILE_TYPES=*
MAX_FILE_SIZE_MB=2048
BLOCKED_FILE_TYPES=application/x-executable,application/x-dosexec,application/x-msdos-program,application/x-sh
```

### Profile Pictures Only
```bash
ALLOWED_FILE_TYPES=image/jpeg,image/png,image/webp
MAX_FILE_SIZE_MB=5
```

## Common MIME Types Reference

### Images
- `image/jpeg` - JPEG images
- `image/png` - PNG images
- `image/gif` - GIF animations
- `image/webp` - WebP images
- `image/svg+xml` - SVG vector graphics
- `image/bmp` - Bitmap images
- `image/tiff` - TIFF images

### Videos
- `video/mp4` - MP4 videos
- `video/mpeg` - MPEG videos
- `video/quicktime` - QuickTime/MOV videos
- `video/x-msvideo` - AVI videos
- `video/webm` - WebM videos
- `video/x-matroska` - MKV videos

### Audio
- `audio/mpeg` - MP3 audio
- `audio/wav` - WAV audio
- `audio/ogg` - OGG audio
- `audio/aac` - AAC audio
- `audio/webm` - WebM audio
- `audio/flac` - FLAC lossless audio
- `audio/x-m4a` - M4A audio

### Documents
- `application/pdf` - PDF documents
- `application/msword` - Word 97-2003 (.doc)
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` - Word 2007+ (.docx)
- `application/vnd.ms-excel` - Excel 97-2003 (.xls)
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` - Excel 2007+ (.xlsx)
- `application/vnd.ms-powerpoint` - PowerPoint 97-2003 (.ppt)
- `application/vnd.openxmlformats-officedocument.presentationml.presentation` - PowerPoint 2007+ (.pptx)

### Text Files
- `text/plain` - Plain text (.txt)
- `text/csv` - CSV files
- `text/markdown` - Markdown files
- `text/html` - HTML files
- `application/json` - JSON files
- `application/xml` - XML files
- `text/xml` - XML text files

### Archives
- `application/zip` - ZIP archives
- `application/x-rar-compressed` - RAR archives
- `application/x-7z-compressed` - 7-Zip archives
- `application/x-tar` - TAR archives
- `application/gzip` - GZIP archives

### Code Files
- `text/x-python` - Python source
- `text/javascript` - JavaScript source
- `application/javascript` - JavaScript application
- `text/x-java-source` - Java source
- `text/x-c` - C source
- `text/x-c++` - C++ source

## Security Considerations

### Always Block Executables
The default `BLOCKED_FILE_TYPES` blocks common executable formats:
- Windows executables (.exe, .dll, .bat, .cmd)
- Linux/Unix executables and scripts
- macOS applications

**Never remove these from the blocked list** unless you have specific security measures in place.

### Additional Security Recommendations

1. **Validate on server side**: Never trust client-provided MIME types. The backend validates actual content.

2. **Use virus scanning**: Consider integrating virus scanning for uploaded files (ClamAV, etc.)

3. **Store files outside web root**: The default configuration stores files in MinIO/S3, not in the web-accessible directory.

4. **Use presigned URLs**: Files are accessed via time-limited presigned URLs, not direct links.

5. **Implement file scanning**: For production systems, implement malware scanning on uploads.

## Testing Configuration

After changing configuration, test file uploads:

```bash
# Test with allowed file type
python cli.py files upload test.txt

# Test with video file (if allowed)
python cli.py files upload video.mp4

# Test with blocked file type (should fail)
python cli.py files upload malware.exe
```

## API Response Codes

- `201 Created` - File uploaded successfully
- `413 Payload Too Large` - File exceeds `MAX_FILE_SIZE_MB`
- `415 Unsupported Media Type` - File type not allowed or blocked for security
- `500 Internal Server Error` - Storage error (check MinIO/S3 configuration)

## Troubleshooting

### Files Being Rejected
1. Check `ALLOWED_FILE_TYPES` in `.env`
2. Verify file MIME type matches allowed types
3. Check if file type is in `BLOCKED_FILE_TYPES`
4. Test with `ALLOWED_FILE_TYPES=*` to allow all types

### Unknown MIME Types
Some files may have unusual MIME types. Use a tool to check:
```bash
file --mime-type your-file.ext
```

Then add that MIME type to your `ALLOWED_FILE_TYPES` configuration.

### Storage Provider Errors
If files are rejected with 500 errors, check:
1. MinIO/S3 is running: `docker-compose ps`
2. Credentials are correct in `.env`
3. Bucket exists or auto-creation is enabled
4. Storage provider has sufficient disk space
