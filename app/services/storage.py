"""File storage service with S3 and local storage support."""

import hashlib
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Tuple

import boto3
from botocore.exceptions import ClientError
from PIL import Image

from app.core.config import settings


class StorageService:
    """Abstract storage service interface."""

    async def upload(
        self, file: BinaryIO, filename: str, content_type: str
    ) -> Tuple[str, str]:
        """
        Upload file to storage.

        Args:
            file: File-like object
            filename: Filename
            content_type: MIME type

        Returns:
            Tuple of (storage_path, provider)
        """
        raise NotImplementedError

    async def download(self, storage_path: str) -> bytes:
        """
        Download file from storage.

        Args:
            storage_path: Path to file in storage

        Returns:
            File contents as bytes
        """
        raise NotImplementedError

    async def delete(self, storage_path: str) -> None:
        """
        Delete file from storage.

        Args:
            storage_path: Path to file in storage
        """
        raise NotImplementedError

    async def get_presigned_url(
        self, storage_path: str, expiration: int = 3600
    ) -> str:
        """
        Get presigned URL for file download.

        Args:
            storage_path: Path to file in storage
            expiration: URL expiration in seconds

        Returns:
            Presigned URL
        """
        raise NotImplementedError


class S3StorageService(StorageService):
    """S3-based file storage service."""

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
    ):
        """Initialize S3 storage service."""
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

    async def upload(
        self, file: BinaryIO, filename: str, content_type: str
    ) -> Tuple[str, str]:
        """Upload file to S3."""
        # Generate unique S3 key
        file_ext = Path(filename).suffix
        s3_key = f"uploads/{uuid.uuid4()}{file_ext}"

        try:
            # Upload to S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": content_type},
            )

            return s3_key, "s3"

        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")

    async def download(self, storage_path: str) -> bytes:
        """Download file from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=storage_path)
            return response["Body"].read()

        except ClientError as e:
            raise Exception(f"Failed to download from S3: {e}")

    async def delete(self, storage_path: str) -> None:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=storage_path)

        except ClientError as e:
            raise Exception(f"Failed to delete from S3: {e}")

    async def get_presigned_url(
        self, storage_path: str, expiration: int = 3600
    ) -> str:
        """Get presigned URL for S3 object."""
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": storage_path},
                ExpiresIn=expiration,
            )
            return url

        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {e}")


class LocalStorageService(StorageService):
    """Local filesystem storage service."""

    def __init__(self, base_path: str = "uploads"):
        """Initialize local storage service."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(
        self, file: BinaryIO, filename: str, content_type: str
    ) -> Tuple[str, str]:
        """Upload file to local filesystem."""
        # Generate unique filename
        file_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"

        # Create subdirectory based on first 2 chars of UUID (for better file organization)
        subdir = unique_filename[:2]
        upload_dir = self.base_path / subdir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = upload_dir / unique_filename
        with open(file_path, "wb") as f:
            f.write(file.read())

        # Return relative path
        relative_path = f"{subdir}/{unique_filename}"
        return relative_path, "local"

    async def download(self, storage_path: str) -> bytes:
        """Download file from local filesystem."""
        file_path = self.base_path / storage_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        with open(file_path, "rb") as f:
            return f.read()

    async def delete(self, storage_path: str) -> None:
        """Delete file from local filesystem."""
        file_path = self.base_path / storage_path

        if file_path.exists():
            file_path.unlink()

    async def get_presigned_url(
        self, storage_path: str, expiration: int = 3600
    ) -> str:
        """
        Get URL for local file.

        Note: For local storage, this returns a path. In production,
        you'd use a reverse proxy to serve these files.
        """
        return f"/files/{storage_path}"


class FileStorageService:
    """Unified file storage service with automatic provider selection."""

    def __init__(self):
        """Initialize storage service based on configuration."""
        # Determine storage provider from environment
        storage_provider = os.getenv("FILE_STORAGE_PROVIDER", "local")

        if storage_provider == "s3":
            bucket_name = os.getenv("AWS_S3_BUCKET", "")
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_region = os.getenv("AWS_REGION", "us-east-1")

            if not bucket_name:
                raise ValueError("AWS_S3_BUCKET environment variable not set")

            self.provider: StorageService = S3StorageService(
                bucket_name=bucket_name,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
            )
        else:
            upload_dir = os.getenv("LOCAL_UPLOAD_DIR", "uploads")
            self.provider = LocalStorageService(base_path=upload_dir)

    @staticmethod
    def calculate_checksum(file: BinaryIO) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        file.seek(0)

        while chunk := file.read(8192):
            sha256.update(chunk)

        file.seek(0)
        return sha256.hexdigest()

    @staticmethod
    def validate_file_type(content_type: str, allowed_types: list[str]) -> bool:
        """Validate file content type."""
        return content_type in allowed_types

    @staticmethod
    def validate_file_size(size: int, max_size: int) -> bool:
        """Validate file size."""
        return size <= max_size

    @staticmethod
    def optimize_image(file: BinaryIO, max_width: int = 1920) -> BinaryIO:
        """
        Optimize image by resizing and compressing.

        Args:
            file: Image file
            max_width: Maximum width in pixels

        Returns:
            Optimized image file
        """
        from io import BytesIO

        img = Image.open(file)

        # Convert RGBA to RGB if necessary
        if img.mode == "RGBA":
            img = img.convert("RGB")

        # Resize if needed
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save optimized image
        output = BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        output.seek(0)

        return output

    async def upload(
        self, file: BinaryIO, filename: str, content_type: str
    ) -> Tuple[str, str, str]:
        """
        Upload file to storage.

        Args:
            file: File-like object
            filename: Original filename
            content_type: MIME type

        Returns:
            Tuple of (storage_path, provider, checksum)
        """
        # Calculate checksum
        checksum = self.calculate_checksum(file)

        # Upload to provider
        storage_path, provider = await self.provider.upload(file, filename, content_type)

        return storage_path, provider, checksum

    async def download(self, storage_path: str) -> bytes:
        """Download file from storage."""
        return await self.provider.download(storage_path)

    async def delete(self, storage_path: str) -> None:
        """Delete file from storage."""
        await self.provider.delete(storage_path)

    async def get_presigned_url(
        self, storage_path: str, expiration: int = 3600
    ) -> str:
        """Get presigned URL for file."""
        return await self.provider.get_presigned_url(storage_path, expiration)


# Global storage service instance
storage_service = FileStorageService()
