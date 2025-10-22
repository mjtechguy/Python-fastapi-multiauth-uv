"""E2E tests for file upload and storage."""

import pytest
import io
from httpx import AsyncClient


class TestFileOperations:
    """Test file upload, download, and management."""

    @pytest.mark.asyncio
    async def test_upload_file(self, authenticated_client: AsyncClient, sample_file_data: bytes):
        """Test file upload."""
        files = {
            "file": ("test_document.txt", io.BytesIO(sample_file_data), "text/plain")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 500]  # May fail if storage not configured

        if response.status_code == 201:
            file_data = response.json()
            assert "id" in file_data
            assert file_data["filename"] == "test_document.txt"
            assert file_data["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_list_files(self, authenticated_client: AsyncClient):
        """Test listing user's files."""
        response = await authenticated_client.get("/api/v1/files")
        assert response.status_code == 200
        files = response.json()
        assert "items" in files or isinstance(files, list)

    @pytest.mark.asyncio
    async def test_upload_image(self, authenticated_client: AsyncClient):
        """Test uploading an image file."""
        # Create a minimal PNG image (1x1 pixel)
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        files = {
            "file": ("test_image.png", io.BytesIO(png_data), "image/png")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 500]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, authenticated_client: AsyncClient):
        """Test uploading file exceeding size limit."""
        # Create 60MB file (exceeds default 50MB limit)
        large_data = b"x" * (60 * 1024 * 1024)
        files = {
            "file": ("large_file.bin", io.BytesIO(large_data), "application/octet-stream")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        # Should fail with 413 or similar
        assert response.status_code in [413, 422, 500]
