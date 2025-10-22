"""Organization service for multi-tenancy operations."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization
from app.models.user import User, user_organizations
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    """Service for organization management."""

    @staticmethod
    async def create(
        db: AsyncSession, org_in: OrganizationCreate, owner_id: UUID
    ) -> Organization:
        """Create a new organization."""
        org = Organization(
            name=org_in.name,
            slug=org_in.slug,
            description=org_in.description,
            owner_id=owner_id,
        )
        db.add(org)
        await db.flush()

        # Add owner as member
        await db.execute(
            user_organizations.insert().values(user_id=owner_id, organization_id=org.id)
        )

        await db.flush()
        await db.refresh(org)
        return org

    @staticmethod
    async def get_by_id(db: AsyncSession, org_id: UUID) -> Organization | None:
        """Get organization by ID."""
        result = await db.execute(
            select(Organization)
            .options(selectinload(Organization.members), selectinload(Organization.teams))
            .where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(db: AsyncSession, slug: str) -> Organization | None:
        """Get organization by slug."""
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession, org: Organization, org_in: OrganizationUpdate
    ) -> Organization:
        """Update organization information."""
        update_data = org_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)

        await db.flush()
        await db.refresh(org)
        return org

    @staticmethod
    async def delete(db: AsyncSession, org: Organization) -> None:
        """Delete organization."""
        await db.delete(org)
        await db.flush()

    @staticmethod
    async def add_member(db: AsyncSession, org_id: UUID, user_id: UUID) -> None:
        """Add a member to the organization."""
        await db.execute(
            user_organizations.insert().values(user_id=user_id, organization_id=org_id)
        )
        await db.flush()

    @staticmethod
    async def remove_member(db: AsyncSession, org_id: UUID, user_id: UUID) -> None:
        """Remove a member from the organization."""
        await db.execute(
            user_organizations.delete().where(
                user_organizations.c.user_id == user_id,
                user_organizations.c.organization_id == org_id,
            )
        )
        await db.flush()

    @staticmethod
    async def is_member(db: AsyncSession, org_id: UUID, user_id: UUID) -> bool:
        """Check if user is a member of the organization."""
        result = await db.execute(
            select(user_organizations).where(
                user_organizations.c.user_id == user_id,
                user_organizations.c.organization_id == org_id,
            )
        )
        return result.first() is not None

    @staticmethod
    async def list_user_organizations(
        db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Organization], int]:
        """List organizations for a user."""
        count_result = await db.execute(
            select(func.count(Organization.id))
            .join(user_organizations)
            .where(user_organizations.c.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Organization)
            .join(user_organizations)
            .where(user_organizations.c.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        organizations = result.scalars().all()

        return list(organizations), total

    @staticmethod
    async def list_organizations(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> tuple[list[Organization], int]:
        """List all organizations with pagination."""
        count_result = await db.execute(select(func.count(Organization.id)))
        total = count_result.scalar_one()

        result = await db.execute(select(Organization).offset(skip).limit(limit))
        organizations = result.scalars().all()

        return list(organizations), total
