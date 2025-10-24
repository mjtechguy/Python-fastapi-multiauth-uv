"""Team service for team management operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team
from app.models.user import User, user_teams
from app.schemas.team import TeamCreate, TeamUpdate


class TeamService:
    """Service for team management."""

    @staticmethod
    async def create(
        db: AsyncSession, team_in: TeamCreate, creator_id: UUID
    ) -> Team:
        """Create a new team within an organization."""
        team = Team(
            name=team_in.name,
            slug=team_in.slug,
            description=team_in.description,
            organization_id=team_in.organization_id,
        )
        db.add(team)
        await db.flush()
        await db.refresh(team)
        return team

    @staticmethod
    async def get_by_id(db: AsyncSession, team_id: UUID) -> Team | None:
        """Get team by ID."""
        result = await db.execute(
            select(Team)
            .options(selectinload(Team.members), selectinload(Team.organization))
            .where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(
        db: AsyncSession, slug: str, organization_id: UUID
    ) -> Team | None:
        """Get team by slug within an organization."""
        result = await db.execute(
            select(Team).where(
                Team.slug == slug, Team.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, team: Team, team_in: TeamUpdate) -> Team:
        """Update team information."""
        update_data = team_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(team, field, value)

        await db.flush()
        await db.refresh(team)
        return team

    @staticmethod
    async def delete(db: AsyncSession, team: Team) -> None:
        """Delete team."""
        await db.delete(team)
        await db.flush()

    @staticmethod
    async def add_member(db: AsyncSession, team_id: UUID, user_id: UUID) -> None:
        """Add a member to the team."""
        await db.execute(
            user_teams.insert().values(user_id=user_id, team_id=team_id)
        )
        await db.flush()

    @staticmethod
    async def remove_member(db: AsyncSession, team_id: UUID, user_id: UUID) -> None:
        """Remove a member from the team."""
        await db.execute(
            user_teams.delete().where(
                user_teams.c.user_id == user_id, user_teams.c.team_id == team_id
            )
        )
        await db.flush()

    @staticmethod
    async def is_member(db: AsyncSession, team_id: UUID, user_id: UUID) -> bool:
        """Check if user is a member of the team."""
        result = await db.execute(
            select(user_teams).where(
                user_teams.c.user_id == user_id, user_teams.c.team_id == team_id
            )
        )
        return result.first() is not None

    @staticmethod
    async def list_organization_teams(
        db: AsyncSession, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Team], int]:
        """List teams within an organization."""
        count_result = await db.execute(
            select(func.count(Team.id)).where(Team.organization_id == organization_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Team)
            .where(Team.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        teams = result.scalars().all()

        return list(teams), total

    @staticmethod
    async def list_user_teams(
        db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Team], int]:
        """List teams for a user."""
        count_result = await db.execute(
            select(func.count(Team.id))
            .join(user_teams)
            .where(user_teams.c.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Team)
            .join(user_teams)
            .where(user_teams.c.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        teams = result.scalars().all()

        return list(teams), total

    @staticmethod
    async def get_member_count(db: AsyncSession, team_id: UUID) -> int:
        """Get the number of members in a team."""
        result = await db.execute(
            select(func.count(user_teams.c.user_id)).where(
                user_teams.c.team_id == team_id
            )
        )
        return result.scalar_one()

    @staticmethod
    async def list_team_members(
        db: AsyncSession, team_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[User], int]:
        """List members of a team."""
        count_result = await db.execute(
            select(func.count(User.id))
            .join(user_teams)
            .where(user_teams.c.team_id == team_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(User)
            .join(user_teams)
            .where(user_teams.c.team_id == team_id)
            .offset(skip)
            .limit(limit)
        )
        members = result.scalars().all()

        return list(members), total
