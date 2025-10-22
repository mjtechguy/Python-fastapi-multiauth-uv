"""File upload and management endpoints."""

from typing import Annotated
from uuid import UUID
from math import ceil

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
    Query,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.file import File as FileModel
from app.models.user import User
from app.schemas.file import (
    FileUploadResponse,
    FileResponse,
    FileListResponse,
    FileDownloadResponse,
)
from app.services.storage import storage_service
from app.core.config import settings

router = APIRouter(prefix="/files", tags=["files"])

# Default allowed file types (used when ALLOWED_FILE_TYPES is not set in .env)
DEFAULT_ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
DEFAULT_ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # Excel
    "application/vnd.ms-excel",  # Excel (old)
    "text/plain",  # Text files
    "text/csv",  # CSV files
    "text/markdown",  # Markdown files
    "application/json",  # JSON files
]
DEFAULT_ALLOWED_TYPES = DEFAULT_ALLOWED_IMAGE_TYPES + DEFAULT_ALLOWED_DOCUMENT_TYPES


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    organization_id: UUID | None = Query(None, description="Optional organization ID to store file under"),
) -> FileModel:
    """
    Upload a file.

    Supports images and documents up to configured size limit.
    File type restrictions can be configured via ALLOWED_FILE_TYPES and BLOCKED_FILE_TYPES in .env

    Files are stored in a hierarchical structure:
    - With org: uploads/org_<org_id>/user_<user_id>/filename
    - Without org: uploads/user_<user_id>/filename
    """
    # Validate file size
    content = await file.read()
    file_size = len(content)
    max_file_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if not storage_service.validate_file_size(file_size, max_file_size):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Validate file type
    content_type = file.content_type or "application/octet-stream"

    # Check blocked types first (security)
    blocked_types = settings.blocked_file_types_list
    if content_type in blocked_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {content_type} is blocked for security reasons",
        )

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
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {content_type} not supported",
            )

    # Create file-like object
    from io import BytesIO

    file_obj = BytesIO(content)

    # Optimize images
    if content_type in DEFAULT_ALLOWED_IMAGE_TYPES:
        file_obj = storage_service.optimize_image(file_obj)
        file_size = len(file_obj.getvalue())

    # Determine organization: use provided one or user's default org
    from app.services.organization import OrganizationService

    if organization_id:
        # Verify organization membership if organization_id provided
        is_member = await OrganizationService.is_member(db, organization_id, current_user.id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of the specified organization",
            )
        final_org_id = organization_id
    else:
        # Use user's default organization
        default_org = await OrganizationService.get_or_create_default(db)
        final_org_id = default_org.id

    # Upload to storage with org/user path structure
    try:
        storage_path, provider, checksum = await storage_service.upload(
            file_obj,
            file.filename or "unnamed",
            content_type,
            org_id=str(final_org_id),
            user_id=str(current_user.id),
        )

        # Create database record
        file_record = FileModel(
            filename=file.filename or "unnamed",
            original_filename=file.filename or "unnamed",
            content_type=content_type,
            size=file_size,
            storage_path=storage_path,
            storage_provider=provider,
            uploaded_by_id=current_user.id,
            organization_id=final_org_id,
            checksum=checksum,
        )

        if provider == "s3":
            import os

            file_record.bucket_name = os.getenv("AWS_S3_BUCKET")
            file_record.s3_key = storage_path

        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)

        return file_record

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )


@router.get("", response_model=FileListResponse)
async def list_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> FileListResponse:
    """List files uploaded by the current user."""
    skip = (page - 1) * page_size

    # Get total count
    count_result = await db.execute(
        select(func.count(FileModel.id)).where(
            FileModel.uploaded_by_id == current_user.id,
            FileModel.is_deleted == False,
        )
    )
    total = count_result.scalar_one()

    # Get files
    result = await db.execute(
        select(FileModel)
        .where(
            FileModel.uploaded_by_id == current_user.id,
            FileModel.is_deleted == False,
        )
        .offset(skip)
        .limit(page_size)
    )
    files = result.scalars().all()

    return FileListResponse(
        items=list(files),
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size),
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileModel:
    """Get file metadata."""
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check permission
    if file.uploaded_by_id != current_user.id and not file.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    return file


@router.get("/{file_id}/download", response_model=FileDownloadResponse)
async def get_download_url(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    expires_in: int = Query(3600, ge=60, le=86400),
) -> FileDownloadResponse:
    """
    Get presigned URL for file download.

    URL expires after specified time (default 1 hour, max 24 hours).
    """
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check permission
    if file.uploaded_by_id != current_user.id and not file.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file",
        )

    # Generate presigned URL
    try:
        download_url = await storage_service.get_presigned_url(
            file.storage_path, expiration=expires_in
        )

        return FileDownloadResponse(
            download_url=download_url,
            expires_in=expires_in,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}",
        )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Delete a file (soft delete).

    File is marked as deleted but not immediately removed from storage.
    """
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check permission
    if file.uploaded_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this file",
        )

    # Soft delete
    file.is_deleted = True
    await db.commit()
