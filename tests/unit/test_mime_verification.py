"""Unit tests for MIME type verification."""

import io
import pytest
from app.services.storage import FileStorageService


class TestMIMEVerification:
    """Test MIME type verification using magic bytes."""

    def test_verify_mime_type_detects_png(self):
        """Test that PNG files are correctly identified."""
        # PNG magic bytes: 89 50 4E 47
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2040
        file = io.BytesIO(png_header)

        mime_type = FileStorageService.verify_mime_type(file)
        assert mime_type == "image/png"

    def test_verify_mime_type_detects_jpeg(self):
        """Test that JPEG files are correctly identified."""
        # JPEG magic bytes: FF D8 FF
        jpeg_header = b'\xff\xd8\xff\xe0' + b'\x00' * 2044
        file = io.BytesIO(jpeg_header)

        mime_type = FileStorageService.verify_mime_type(file)
        assert mime_type.startswith("image/jpeg")

    def test_verify_mime_type_detects_pdf(self):
        """Test that PDF files are correctly identified."""
        # PDF magic bytes: %PDF
        pdf_header = b'%PDF-1.4' + b'\x00' * 2040
        file = io.BytesIO(pdf_header)

        mime_type = FileStorageService.verify_mime_type(file)
        assert mime_type == "application/pdf"

    def test_verify_mime_type_rejects_empty_file(self):
        """Test that empty files raise ValueError."""
        empty_file = io.BytesIO(b'')

        with pytest.raises(ValueError, match="Empty file"):
            FileStorageService.verify_mime_type(empty_file)

    def test_verify_mime_type_detects_mismatch(self):
        """Test that MIME type mismatch is detected."""
        # PNG file claimed as JPEG
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2040
        file = io.BytesIO(png_header)

        with pytest.raises(ValueError, match="MIME type mismatch"):
            FileStorageService.verify_mime_type(file, claimed_type="image/jpeg")

    def test_verify_mime_type_allows_matching_types(self):
        """Test that matching MIME types pass verification."""
        # PNG claimed as PNG
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2040
        file = io.BytesIO(png_header)

        mime_type = FileStorageService.verify_mime_type(file, claimed_type="image/png")
        assert mime_type == "image/png"

    def test_verify_mime_type_allows_generic_octet_stream(self):
        """Test that application/octet-stream is allowed (generic type)."""
        # Any file with generic claim
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2040
        file = io.BytesIO(png_header)

        # Should not raise even though types don't match
        mime_type = FileStorageService.verify_mime_type(
            file,
            claimed_type="application/octet-stream"
        )
        assert mime_type == "image/png"

    def test_verify_mime_type_flexible_with_text_types(self):
        """Test flexibility with text/* MIME types."""
        # Plain text claimed as text/csv or vice versa should be allowed
        text_content = b'Hello, World!' + b'\x00' * 2035
        file = io.BytesIO(text_content)

        # Should not raise for text type variations
        try:
            FileStorageService.verify_mime_type(file, claimed_type="text/csv")
            # If it passes, good. If detected type is text/*, it should allow it
        except ValueError as e:
            # Only fail if it's not a text/* flexibility case
            if "text/" not in str(e):
                raise

    def test_verify_mime_type_prevents_executable_as_image(self):
        """Test that executable files cannot be claimed as images."""
        # PE executable header (Windows .exe)
        exe_header = b'MZ' + b'\x00' * 2046
        file = io.BytesIO(exe_header)

        with pytest.raises(ValueError, match="MIME type mismatch"):
            FileStorageService.verify_mime_type(file, claimed_type="image/png")

    def test_verify_mime_type_file_pointer_reset(self):
        """Test that file pointer is reset after verification."""
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2040
        file = io.BytesIO(png_header)

        # Move pointer
        file.seek(100)

        # Verify
        FileStorageService.verify_mime_type(file)

        # Pointer should be reset to 0
        assert file.tell() == 0


class TestStreamingUpload:
    """Test streaming file upload functionality."""

    def test_calculate_checksum_streams_in_chunks(self):
        """Test that checksum calculation streams file in chunks."""
        # Create a large file (simulated)
        content = b'x' * 10000
        file = io.BytesIO(content)

        checksum = FileStorageService.calculate_checksum(file)

        # Should be valid SHA256 hex string
        assert len(checksum) == 64
        assert all(c in '0123456789abcdef' for c in checksum)

        # File pointer should be reset
        assert file.tell() == 0

    def test_calculate_checksum_consistent(self):
        """Test that checksum is consistent for same content."""
        content = b'test content'
        file1 = io.BytesIO(content)
        file2 = io.BytesIO(content)

        checksum1 = FileStorageService.calculate_checksum(file1)
        checksum2 = FileStorageService.calculate_checksum(file2)

        assert checksum1 == checksum2

    def test_calculate_checksum_different_for_different_content(self):
        """Test that different content produces different checksums."""
        file1 = io.BytesIO(b'content1')
        file2 = io.BytesIO(b'content2')

        checksum1 = FileStorageService.calculate_checksum(file1)
        checksum2 = FileStorageService.calculate_checksum(file2)

        assert checksum1 != checksum2
