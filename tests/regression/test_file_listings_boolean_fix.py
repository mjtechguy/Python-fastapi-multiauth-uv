"""Regression test for file listings boolean comparison fix.

Issue: Using 'not FileModel.is_deleted' triggered SQLAlchemy's
"Boolean value of this clause is not defined" error, crashing file
listings and counts.

Fix: Changed to FileModel.is_deleted.is_(False)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File as FileModel
from app.models.user import User


@pytest.mark.asyncio
class TestFileListingsBooleanFix:
    """Test that file listings correctly exclude deleted files using proper SQLAlchemy syntax."""

    async def test_file_list_excludes_deleted_files(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that GET /files returns only non-deleted files.

        This tests the fix for the boolean comparison issue.
        """
        # Create 3 active files
        active_files = []
        for i in range(3):
            file = FileModel(
                filename=f"active_file_{i}.txt",
                original_filename=f"active_{i}.txt",
                file_path=f"/uploads/active_{i}.txt",
                file_size=1024 * (i + 1),
                content_type="text/plain",
                uploaded_by_id=test_user.id,
                is_deleted=False,
            )
            db_session.add(file)
            active_files.append(file)

        # Create 2 deleted files
        deleted_files = []
        for i in range(2):
            file = FileModel(
                filename=f"deleted_file_{i}.txt",
                original_filename=f"deleted_{i}.txt",
                file_path=f"/uploads/deleted_{i}.txt",
                file_size=512 * (i + 1),
                content_type="text/plain",
                uploaded_by_id=test_user.id,
                is_deleted=True,  # Soft-deleted
            )
            db_session.add(file)
            deleted_files.append(file)

        await db_session.commit()

        # Make API request to list files
        response = await authenticated_client.get("/api/v1/files?page=1&page_size=10")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()

        # Should only return active files (3), not deleted ones (2)
        assert data["total"] == 3, f"Expected 3 active files, got {data['total']}"
        assert len(data["items"]) == 3, f"Expected 3 items, got {len(data['items'])}"

        # Verify all returned files are not deleted
        returned_filenames = {item["filename"] for item in data["items"]}
        for i in range(3):
            assert f"active_file_{i}.txt" in returned_filenames

        # Verify deleted files are NOT in results
        for i in range(2):
            assert f"deleted_file_{i}.txt" not in returned_filenames

    async def test_sqlalchemy_boolean_syntax_works(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """
        Regression test: Verify that .is_(False) SQLAlchemy syntax works correctly.

        This would have failed with 'not FileModel.is_deleted' causing
        "Boolean value of this clause is not defined" error.
        """
        # Create test files
        active_file = FileModel(
            filename="test_active.txt",
            original_filename="active.txt",
            file_path="/test/active.txt",
            file_size=100,
            content_type="text/plain",
            uploaded_by_id=test_user.id,
            is_deleted=False,
        )
        deleted_file = FileModel(
            filename="test_deleted.txt",
            original_filename="deleted.txt",
            file_path="/test/deleted.txt",
            file_size=100,
            content_type="text/plain",
            uploaded_by_id=test_user.id,
            is_deleted=True,
        )
        db_session.add(active_file)
        db_session.add(deleted_file)
        await db_session.commit()

        # This is the CORRECT syntax that was fixed
        result = await db_session.execute(
            select(FileModel).where(
                FileModel.uploaded_by_id == test_user.id,
                FileModel.is_deleted.is_(False),  # CORRECT
            )
        )
        files = result.scalars().all()

        assert len(files) == 1
        assert files[0].filename == "test_active.txt"

        # Verify the old broken syntax would have failed
        # (We don't actually test it, just document what would have broken)
        # result = await db_session.execute(
        #     select(FileModel).where(
        #         FileModel.uploaded_by_id == test_user.id,
        #         not FileModel.is_deleted,  # BROKEN - would raise error
        #     )
        # )

    async def test_file_count_excludes_deleted(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that the total count in pagination excludes deleted files.
        """
        # Create 10 active files
        for i in range(10):
            file = FileModel(
                filename=f"count_active_{i}.txt",
                original_filename=f"active_{i}.txt",
                file_path=f"/count/active_{i}.txt",
                file_size=100,
                content_type="text/plain",
                uploaded_by_id=test_user.id,
                is_deleted=False,
            )
            db_session.add(file)

        # Create 5 deleted files
        for i in range(5):
            file = FileModel(
                filename=f"count_deleted_{i}.txt",
                original_filename=f"deleted_{i}.txt",
                file_path=f"/count/deleted_{i}.txt",
                file_size=100,
                content_type="text/plain",
                uploaded_by_id=test_user.id,
                is_deleted=True,
            )
            db_session.add(file)

        await db_session.commit()

        # Request first page (5 items per page)
        response = await authenticated_client.get("/api/v1/files?page=1&page_size=5")

        assert response.status_code == 200
        data = response.json()

        # Total should be 10 (active only), not 15 (active + deleted)
        assert data["total"] == 10
        assert len(data["items"]) == 5  # First page
        assert data["page"] == 1
        assert data["page_size"] == 5

    async def test_pagination_with_deleted_files(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that pagination works correctly when some files are deleted.
        """
        # Create files: active, deleted, active, deleted, active pattern
        for i in range(15):
            file = FileModel(
                filename=f"pagination_file_{i}.txt",
                original_filename=f"file_{i}.txt",
                file_path=f"/pagination/file_{i}.txt",
                file_size=100,
                content_type="text/plain",
                uploaded_by_id=test_user.id,
                is_deleted=(i % 2 == 1),  # Every other file is deleted
            )
            db_session.add(file)

        await db_session.commit()

        # Should have 8 active files (0, 2, 4, 6, 8, 10, 12, 14)
        # and 7 deleted files (1, 3, 5, 7, 9, 11, 13)

        # Get all files with large page size
        response = await authenticated_client.get("/api/v1/files?page=1&page_size=20")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 8  # Only active files
        assert len(data["items"]) == 8

        # Verify only even-numbered files (active ones) are returned
        returned_filenames = {item["filename"] for item in data["items"]}
        for i in range(0, 15, 2):  # Even indices (active)
            assert f"pagination_file_{i}.txt" in returned_filenames

        for i in range(1, 15, 2):  # Odd indices (deleted)
            assert f"pagination_file_{i}.txt" not in returned_filenames

    async def test_mixed_users_deleted_files_isolation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test that deleted files are isolated per user.
        User A's deleted files don't affect User B's file listings.
        """
        # Create two users
        from app.services.user import UserService

        user_a = await UserService.create_user(
            db_session,
            email=f"user_a_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="User A",
        )
        user_b = await UserService.create_user(
            db_session,
            email=f"user_b_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="User B",
        )

        # User A: 3 active, 2 deleted
        for i in range(3):
            db_session.add(
                FileModel(
                    filename=f"user_a_active_{i}.txt",
                    original_filename=f"a_active_{i}.txt",
                    file_path=f"/a/active_{i}.txt",
                    file_size=100,
                    content_type="text/plain",
                    uploaded_by_id=user_a.id,
                    is_deleted=False,
                )
            )
        for i in range(2):
            db_session.add(
                FileModel(
                    filename=f"user_a_deleted_{i}.txt",
                    original_filename=f"a_deleted_{i}.txt",
                    file_path=f"/a/deleted_{i}.txt",
                    file_size=100,
                    content_type="text/plain",
                    uploaded_by_id=user_a.id,
                    is_deleted=True,
                )
            )

        # User B: 4 active, 1 deleted
        for i in range(4):
            db_session.add(
                FileModel(
                    filename=f"user_b_active_{i}.txt",
                    original_filename=f"b_active_{i}.txt",
                    file_path=f"/b/active_{i}.txt",
                    file_size=100,
                    content_type="text/plain",
                    uploaded_by_id=user_b.id,
                    is_deleted=False,
                )
            )
        for i in range(1):
            db_session.add(
                FileModel(
                    filename=f"user_b_deleted_{i}.txt",
                    original_filename=f"b_deleted_{i}.txt",
                    file_path=f"/b/deleted_{i}.txt",
                    file_size=100,
                    content_type="text/plain",
                    uploaded_by_id=user_b.id,
                    is_deleted=True,
                )
            )

        await db_session.commit()

        # Verify counts directly in database
        result_a = await db_session.execute(
            select(FileModel).where(
                FileModel.uploaded_by_id == user_a.id,
                FileModel.is_deleted.is_(False),
            )
        )
        user_a_active = result_a.scalars().all()
        assert len(user_a_active) == 3

        result_b = await db_session.execute(
            select(FileModel).where(
                FileModel.uploaded_by_id == user_b.id,
                FileModel.is_deleted.is_(False),
            )
        )
        user_b_active = result_b.scalars().all()
        assert len(user_b_active) == 4
