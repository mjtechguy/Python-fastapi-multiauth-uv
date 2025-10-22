#!/usr/bin/env python3
"""Initialize database with default data."""

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.rbac import RBACService
from app.services.user import UserService
from app.schemas.user import UserCreate


async def init_db() -> None:
    """Initialize database with default roles, permissions, and admin user."""
    async with AsyncSessionLocal() as db:
        try:
            print("Initializing database...")

            # Create default permissions
            print("Creating default permissions...")
            await RBACService.initialize_default_permissions(db)

            # Create default roles
            print("Creating default roles...")
            await RBACService.initialize_default_roles(db)

            # Create admin user if not exists
            admin_email = "admin@example.com"
            existing_admin = await UserService.get_by_email(db, admin_email)

            if not existing_admin:
                print("Creating admin user...")
                admin_user = UserCreate(
                    email=admin_email,
                    username="admin",
                    full_name="System Administrator",
                    password="Admin123!",
                )
                user = await UserService.create(db, admin_user)
                user.is_superuser = True
                user.is_verified = True

                print(f"Admin user created: {admin_email}")
                print("Default password: Admin123!")
                print("⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
            else:
                print("Admin user already exists")

            await db.commit()
            print("✅ Database initialization complete!")

        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(init_db())
