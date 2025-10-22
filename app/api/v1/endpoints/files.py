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

router = APIRouter(prefix="/files", tags=["files"])

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileModel:
    """
    Upload a file.

    Supports images and documents up to 50MB.
    """
    # Validate file size
    content = await file.read()
    file_size = len(content)

    if not storage_service.validate_file_size(file_size, MAX_FILE_SIZE):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024)}MB",
        )

    # Validate file type
    content_type = file.content_type or "application/octet-stream"
    allowed_types = ALLOWED_IMAGE_TYPES + ALLOWED_DOCUMENT_TYPES

    if not storage_service.validate_file_type(content_type, allowed_types):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {content_type} not supported",
        )

    # Create file-like object
    from io import BytesIO

    file_obj = BytesIO(content)

    # Optimize images
    if content_type in ALLOWED_IMAGE_TYPES:
        file_obj = storage_service.optimize_image(file_obj)
        file_size = len(file_obj.getvalue())

    # Upload to storage
    try:
        storage_path, provider, checksum = await storage_service.upload(
            file_obj, file.filename or "unnamed", content_type
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
