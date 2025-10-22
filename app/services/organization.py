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

    DEFAULT_ORG_NAME = "Default Organization"
    DEFAULT_ORG_SLUG = "default"

    @staticmethod
    async def get_or_create_default(db: AsyncSession) -> Organization:
        """Get or create the default organization.

        The default organization is used when users are not explicitly added to an organization.
        It's automatically created on first use.
        """
        # Try to get existing default org
        default_org = await OrganizationService.get_by_slug(db, OrganizationService.DEFAULT_ORG_SLUG)

        if default_org:
            return default_org

        # Create default org with system owner (first user will be owner)
        from app.models.user import User

        # Get first user as owner, or create with None owner_id (will be set later)
        first_user_result = await db.execute(select(User).limit(1))
        first_user = first_user_result.scalar_one_or_none()

        default_org = Organization(
            name=OrganizationService.DEFAULT_ORG_NAME,
            slug=OrganizationService.DEFAULT_ORG_SLUG,
            description="Default organization for all users",
            owner_id=first_user.id if first_user else None,
        )
        db.add(default_org)
        await db.flush()
        await db.refresh(default_org)

        return default_org

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
        """Add a member to the organization.

        Regular users can only be members of one organization at a time.
        Global admins (superusers) can be members of multiple organizations.

        Special behavior for default organization:
        - Users in the default org are automatically moved to the new org
        - Users in other orgs must be explicitly removed first

        Raises:
            ValueError: If user is already a member of a non-default organization and is not a superuser
        """
        # Get user to check if they're a superuser
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Superusers can be in multiple organizations
        if not user.is_superuser:
            # Check if user is already in another organization
            existing_orgs = await db.execute(
                select(user_organizations).where(user_organizations.c.user_id == user_id)
            )
            existing = existing_orgs.first()

            if existing and existing.organization_id != org_id:
                # Get the organization to check if it's the default org
                existing_org_result = await db.execute(
                    select(Organization).where(Organization.id == existing.organization_id)
                )
                existing_org = existing_org_result.scalar_one_or_none()

                # If user is in the default org, automatically move them
                if existing_org and existing_org.slug == OrganizationService.DEFAULT_ORG_SLUG:
                    # Remove from default org
                    await db.execute(
                        user_organizations.delete().where(
                            user_organizations.c.user_id == user_id,
                            user_organizations.c.organization_id == existing.organization_id,
                        )
                    )
                else:
                    # User is in a non-default org, require explicit removal
                    raise ValueError(
                        f"User is already a member of another organization ({existing_org.name if existing_org else 'Unknown'}). "
                        "Regular users can only belong to one organization at a time. "
                        "Remove them from their current organization first, or grant them superuser status."
                    )

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
    async def list_members(db: AsyncSession, org_id: UUID) -> list[User]:
        """List all members of an organization."""
        result = await db.execute(
            select(User)
            .join(user_organizations)
            .where(user_organizations.c.organization_id == org_id)
            .order_by(user_organizations.c.created_at)
        )
        return list(result.scalars().all())

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
