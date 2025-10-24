"""RBAC (Role-Based Access Control) service."""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Permission, Role, RolePermission
from app.models.user import User, user_roles
from app.schemas.role import PermissionCreate, RoleCreate, RoleUpdate


class RBACService:
    """Service for role-based access control operations."""

    @staticmethod
    async def create_permission(
        db: AsyncSession, permission_in: PermissionCreate
    ) -> Permission:
        """Create a new permission."""
        permission = Permission(
            name=permission_in.name,
            resource=permission_in.resource,
            action=permission_in.action,
            description=permission_in.description,
        )
        db.add(permission)
        await db.flush()
        await db.refresh(permission)
        return permission

    @staticmethod
    async def get_permission_by_id(db: AsyncSession, permission_id: UUID) -> Permission | None:
        """Get permission by ID."""
        result = await db.execute(select(Permission).where(Permission.id == permission_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_permission_by_name(db: AsyncSession, name: str) -> Permission | None:
        """Get permission by name."""
        result = await db.execute(select(Permission).where(Permission.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_permissions(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> tuple[list[Permission], int]:
        """List all permissions with pagination."""
        count_result = await db.execute(select(func.count(Permission.id)))
        total = count_result.scalar_one()

        result = await db.execute(select(Permission).offset(skip).limit(limit))
        permissions = result.scalars().all()

        return list(permissions), total

    @staticmethod
    async def create_role(db: AsyncSession, role_in: RoleCreate) -> Role:
        """Create a new role with permissions."""
        role = Role(
            name=role_in.name,
            description=role_in.description,
        )
        db.add(role)
        await db.flush()

        # Add permissions to role
        for permission_id in role_in.permission_ids:
            role_perm = RolePermission(role_id=role.id, permission_id=permission_id)
            db.add(role_perm)

        await db.flush()
        await db.refresh(role, ["permissions"])
        return role

    @staticmethod
    async def get_role_by_id(db: AsyncSession, role_id: UUID) -> Role | None:
        """Get role by ID with permissions."""
        result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
        """Get role by name."""
        result = await db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_role(db: AsyncSession, role: Role, role_in: RoleUpdate) -> Role:
        """Update role information and permissions."""
        update_data = role_in.model_dump(exclude_unset=True, exclude={"permission_ids"})
        for field, value in update_data.items():
            setattr(role, field, value)

        # Update permissions if provided
        if role_in.permission_ids is not None:
            # Remove existing permissions
            await db.execute(
                RolePermission.__table__.delete().where(RolePermission.role_id == role.id)
            )

            # Add new permissions
            for permission_id in role_in.permission_ids:
                role_perm = RolePermission(role_id=role.id, permission_id=permission_id)
                db.add(role_perm)

        await db.flush()
        await db.refresh(role, ["permissions"])
        return role

    @staticmethod
    async def delete_role(db: AsyncSession, role: Role) -> None:
        """Delete a role."""
        if role.is_system:
            raise ValueError("Cannot delete system roles")

        await db.delete(role)
        await db.flush()

    @staticmethod
    async def list_roles(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> tuple[list[Role], int]:
        """List all roles with pagination."""
        count_result = await db.execute(select(func.count(Role.id)))
        total = count_result.scalar_one()

        result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).offset(skip).limit(limit)
        )
        roles = result.scalars().all()

        return list(roles), total

    @staticmethod
    async def assign_role_to_user(
        db: AsyncSession,
        user_id: UUID,
        role_id: UUID,
        organization_id: UUID | None = None,
        team_id: UUID | None = None,
    ) -> None:
        """Assign a role to a user."""
        from app.models.user import user_roles

        await db.execute(
            user_roles.insert().values(
                user_id=user_id,
                role_id=role_id,
                organization_id=organization_id,
                team_id=team_id,
            )
        )
        await db.flush()

    @staticmethod
    async def remove_role_from_user(
        db: AsyncSession, user_id: UUID, role_id: UUID
    ) -> None:
        """Remove a role from a user."""
        from app.models.user import user_roles

        await db.execute(
            user_roles.delete().where(
                and_(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
            )
        )
        await db.flush()

    @staticmethod
    async def check_permission(
        db: AsyncSession,
        user: User,
        resource: str,
        action: str,
        organization_id: UUID | None = None,
        team_id: UUID | None = None,
    ) -> bool:
        """Check if user has permission for a resource action."""
        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Build query to check user's permissions through roles
        query = (
            select(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(Role, RolePermission.role_id == Role.id)
            .join(user_roles, Role.id == user_roles.c.role_id)
            .where(
                and_(
                    user_roles.c.user_id == user.id,
                    Permission.resource == resource,
                    Permission.action == action,
                )
            )
        )

        # Add organization/team context if provided
        if organization_id:
            query = query.where(
                (user_roles.c.organization_id == organization_id)
                | (user_roles.c.organization_id.is_(None))
            )

        if team_id:
            query = query.where(
                (user_roles.c.team_id == team_id) | (user_roles.c.team_id.is_(None))
            )

        result = await db.execute(query)
        permission = result.scalar_one_or_none()

        return permission is not None

    @staticmethod
    async def get_user_permissions(
        db: AsyncSession,
        user_id: UUID,
        organization_id: UUID | None = None,
        team_id: UUID | None = None,
    ) -> list[Permission]:
        """Get all permissions for a user."""
        query = (
            select(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(Role, RolePermission.role_id == Role.id)
            .join(user_roles, Role.id == user_roles.c.role_id)
            .where(user_roles.c.user_id == user_id)
        )

        if organization_id:
            query = query.where(
                (user_roles.c.organization_id == organization_id)
                | (user_roles.c.organization_id.is_(None))
            )

        if team_id:
            query = query.where(
                (user_roles.c.team_id == team_id) | (user_roles.c.team_id.is_(None))
            )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def initialize_default_permissions(db: AsyncSession) -> None:
        """Initialize default permissions for the system."""
        resources = ["users", "organizations", "teams", "roles", "permissions"]
        actions = ["create", "read", "update", "delete"]

        for resource in resources:
            for action in actions:
                name = f"{resource}:{action}"
                existing = await RBACService.get_permission_by_name(db, name)

                if not existing:
                    permission = Permission(
                        name=name,
                        resource=resource,
                        action=action,
                        description=f"Permission to {action} {resource}",
                    )
                    db.add(permission)

        await db.flush()

    @staticmethod
    async def initialize_default_roles(db: AsyncSession) -> None:
        """Initialize default roles for the system."""
        # Get all permissions
        result = await db.execute(select(Permission))
        all_permissions = result.scalars().all()
        {p.name: p for p in all_permissions}

        # Admin role with all permissions
        admin_role = await RBACService.get_role_by_name(db, "admin")
        if not admin_role:
            admin_role = Role(
                name="admin",
                description="Administrator with full access",
                is_system=True,
            )
            db.add(admin_role)
            await db.flush()

            for permission in all_permissions:
                role_perm = RolePermission(role_id=admin_role.id, permission_id=permission.id)
                db.add(role_perm)

        # Member role with limited permissions
        member_role = await RBACService.get_role_by_name(db, "member")
        if not member_role:
            member_role = Role(
                name="member",
                description="Regular member with read access",
                is_system=True,
            )
            db.add(member_role)
            await db.flush()

            # Add read permissions
            read_permissions = [p for p in all_permissions if p.action == "read"]
            for permission in read_permissions:
                role_perm = RolePermission(role_id=member_role.id, permission_id=permission.id)
                db.add(role_perm)

        await db.flush()
