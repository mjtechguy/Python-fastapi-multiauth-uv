"""File schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    id: UUID
    filename: str
    original_filename: str
    content_type: str
    size: int
    storage_path: str
    storage_provider: str
    checksum: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileResponse(BaseModel):
    """Response for file metadata."""

    id: UUID
    filename: str
    original_filename: str
    content_type: str
    size: int
    storage_provider: str
    is_public: bool
    uploaded_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    """Paginated file list response."""

    items: list[FileResponse]
    total: int
    page: int
    page_size: int
    pages: int


class FileDownloadResponse(BaseModel):
    """Response for file download URL."""

    download_url: str
    expires_in: int = 3600
