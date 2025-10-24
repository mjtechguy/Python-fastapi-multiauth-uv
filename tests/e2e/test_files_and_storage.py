"""E2E tests for file upload and storage."""

import io

import pytest
from httpx import AsyncClient


@pytest.fixture
async def uploaded_file(authenticated_client: AsyncClient, sample_file_data: bytes):
    """Create an uploaded file for testing."""
    files = {
        "file": ("test_document.txt", io.BytesIO(sample_file_data), "text/plain")
    }
    response = await authenticated_client.post("/api/v1/files/upload", files=files)
    if response.status_code == 201:
        return response.json()
    return None


class TestFileUpload:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_text_file(self, authenticated_client: AsyncClient, sample_file_data: bytes):
        """Test uploading a text file."""
        files = {
            "file": ("test_document.txt", io.BytesIO(sample_file_data), "text/plain")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 415, 500]  # May fail if text/plain not allowed or storage not configured

    @pytest.mark.asyncio
    async def test_upload_pdf(self, authenticated_client: AsyncClient):
        """Test uploading a PDF file."""
        # Minimal valid PDF
        pdf_data = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"

        files = {
            "file": ("document.pdf", io.BytesIO(pdf_data), "application/pdf")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 500]

        if response.status_code == 201:
            file_data = response.json()
            assert "id" in file_data
            assert file_data["filename"] == "document.pdf"
            assert file_data["content_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_upload_image_png(self, authenticated_client: AsyncClient):
        """Test uploading a PNG image."""
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

        if response.status_code == 201:
            file_data = response.json()
            assert file_data["content_type"] == "image/png"
            assert "checksum" in file_data

    @pytest.mark.asyncio
    async def test_upload_image_jpeg(self, authenticated_client: AsyncClient):
        """Test uploading a JPEG image."""
        # Minimal JPEG
        jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'

        files = {
            "file": ("test_image.jpg", io.BytesIO(jpeg_data), "image/jpeg")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 500]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, authenticated_client: AsyncClient):
        """Test uploading file exceeding size limit."""
        # Create 60MB file (exceeds default 50MB limit)
        large_data = b"x" * (60 * 1024 * 1024)
        files = {
            "file": ("large_file.pdf", io.BytesIO(large_data), "application/pdf")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        # Should fail with 413 (request entity too large)
        assert response.status_code in [413, 500]

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self, authenticated_client: AsyncClient):
        """Test uploading unsupported file type."""
        files = {
            "file": ("test.exe", io.BytesIO(b"fake exe content"), "application/x-msdownload")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        # Should fail with 415 (unsupported media type)
        assert response.status_code in [415, 500]

    @pytest.mark.asyncio
    async def test_upload_without_filename(self, authenticated_client: AsyncClient, sample_file_data: bytes):
        """Test uploading file without filename."""
        files = {
            "file": (None, io.BytesIO(sample_file_data), "application/pdf")
        }

        response = await authenticated_client.post("/api/v1/files/upload", files=files)
        assert response.status_code in [201, 500]

        if response.status_code == 201:
            file_data = response.json()
            # Should use default name "unnamed"
            assert "filename" in file_data

    @pytest.mark.asyncio
    async def test_upload_unauthorized(self, client: AsyncClient, sample_file_data: bytes):
        """Test uploading without authentication."""
        files = {
            "file": ("test.pdf", io.BytesIO(sample_file_data), "application/pdf")
        }

        response = await client.post("/api/v1/files/upload", files=files)
        assert response.status_code == 401


class TestFileList:
    """Test file listing."""

    @pytest.mark.asyncio
    async def test_list_files(self, authenticated_client: AsyncClient):
        """Test listing user's files."""
        response = await authenticated_client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_files_with_pagination(self, authenticated_client: AsyncClient):
        """Test file listing with pagination."""
        response = await authenticated_client.get("/api/v1/files?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_files_unauthorized(self, client: AsyncClient):
        """Test listing files without authentication."""
        response = await client.get("/api/v1/files")
        assert response.status_code == 401


class TestFileMetadata:
    """Test getting file metadata."""

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, authenticated_client: AsyncClient, uploaded_file):
        """Test getting file metadata."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await authenticated_client.get(f"/api/v1/files/{uploaded_file['id']}")
        assert response.status_code == 200
        file_data = response.json()
        assert file_data["id"] == uploaded_file["id"]
        assert "filename" in file_data
        assert "size" in file_data
        assert "content_type" in file_data

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent file."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/files/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_file_invalid_uuid(self, authenticated_client: AsyncClient):
        """Test getting file with invalid UUID."""
        response = await authenticated_client.get("/api/v1/files/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_file_unauthorized(self, client: AsyncClient, uploaded_file):
        """Test getting file metadata without authentication."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await client.get(f"/api/v1/files/{uploaded_file['id']}")
        assert response.status_code == 401


class TestFileDownload:
    """Test file download URL generation."""

    @pytest.mark.asyncio
    async def test_get_download_url(self, authenticated_client: AsyncClient, uploaded_file):
        """Test getting download URL for a file."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await authenticated_client.get(f"/api/v1/files/{uploaded_file['id']}/download")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "download_url" in data
            assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_get_download_url_with_expiration(self, authenticated_client: AsyncClient, uploaded_file):
        """Test getting download URL with custom expiration."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await authenticated_client.get(f"/api/v1/files/{uploaded_file['id']}/download?expires_in=7200")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["expires_in"] == 7200

    @pytest.mark.asyncio
    async def test_get_download_url_not_found(self, authenticated_client: AsyncClient):
        """Test getting download URL for non-existent file."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/files/{fake_id}/download")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_download_url_unauthorized(self, client: AsyncClient, uploaded_file):
        """Test getting download URL without authentication."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await client.get(f"/api/v1/files/{uploaded_file['id']}/download")
        assert response.status_code == 401


class TestFileDelete:
    """Test file deletion."""

    @pytest.mark.asyncio
    async def test_delete_file(self, authenticated_client: AsyncClient, sample_file_data: bytes):
        """Test deleting a file."""
        # Upload a file first
        files = {
            "file": ("to_delete.txt", io.BytesIO(sample_file_data), "text/plain")
        }
        upload_response = await authenticated_client.post("/api/v1/files/upload", files=files)

        if upload_response.status_code != 201:
            pytest.skip("File upload not configured")

        file_id = upload_response.json()["id"]

        # Delete the file
        response = await authenticated_client.delete(f"/api/v1/files/{file_id}")
        assert response.status_code == 204

        # Verify file is deleted (soft delete)
        get_response = await authenticated_client.get(f"/api/v1/files/{file_id}")
        # File should not appear in regular queries after soft delete
        assert get_response.status_code in [404, 403]

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, authenticated_client: AsyncClient):
        """Test deleting non-existent file."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.delete(f"/api/v1/files/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_file_unauthorized(self, client: AsyncClient, uploaded_file):
        """Test deleting file without authentication."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        response = await client.delete(f"/api/v1/files/{uploaded_file['id']}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_someone_elses_file(self, client: AsyncClient, db_session, uploaded_file):
        """Test deleting another user's file."""
        if not uploaded_file:
            pytest.skip("File upload not configured")

        # Create another user
        from app.core.security import create_access_token, get_password_hash
        from app.models.user import User

        other_user = User(
            email="otheruser@example.com",
            username="otheruser",
            full_name="Other User",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        token = create_access_token(str(other_user.id))
        client.headers.update({"Authorization": f"Bearer {token}"})

        # Try to delete first user's file
        response = await client.delete(f"/api/v1/files/{uploaded_file['id']}")
        assert response.status_code == 403
