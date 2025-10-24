"""Session management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.session import SessionListResponse, SessionResponse, SessionStatsResponse
from app.services.session import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionListResponse:
    """
    List all active sessions for the current user.

    Shows device information and last activity for each session.
    """
    sessions = await SessionService.get_user_sessions(db, current_user.id)

    # Get current session token from request (if available)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        auth_header.split(" ")[1]

    # Mark current session
    session_responses = []
    for session in sessions:
        session_dict = SessionResponse.model_validate(session).model_dump()

        # Check if this is the current session (simplified check)
        # In production, you'd want a more robust way to identify the current session
        session_dict["is_current"] = (
            session.last_activity == max(s.last_activity for s in sessions)
        )

        session_responses.append(SessionResponse(**session_dict))

    return SessionListResponse(
        sessions=session_responses,
        total=len(sessions),
        active=len([s for s in sessions if s.is_valid]),
    )


@router.get("/stats", response_model=SessionStatsResponse)
async def get_session_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionStatsResponse:
    """Get session statistics for the current user."""
    stats = await SessionService.get_session_count(db, current_user.id)

    return SessionStatsResponse(
        total=stats["total"],
        active=stats["active"],
        devices=stats["devices"],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Revoke a specific session.

    Useful for logging out from a specific device.
    """
    # Get the session to verify ownership
    sessions = await SessionService.get_user_sessions(db, current_user.id, include_expired=True)
    session_ids = [s.id for s in sessions]

    if session_id not in session_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    success = await SessionService.revoke_session(db, session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await db.commit()


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    keep_current: bool = True,
) -> None:
    """
    Revoke all sessions except optionally the current one.

    Useful for "logout from all devices" functionality.
    """
    # If keep_current is True, we need to identify the current session
    # This is simplified - in production you'd track the current session ID
    current_session_id = None
    if keep_current:
        sessions = await SessionService.get_user_sessions(db, current_user.id)
        if sessions:
            # Keep the most recently active session
            current_session_id = max(sessions, key=lambda s: s.last_activity).id

    await SessionService.revoke_all_user_sessions(
        db, current_user.id, except_session_id=current_session_id
    )
    await db.commit()
