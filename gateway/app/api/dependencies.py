"""FastAPI dependencies for authentication, database, etc."""
from typing import Optional

from app.core.config import get_settings
from app.core.security import decode_access_token, verify_api_key
from app.db.base import get_db
from app.models import Agent, AgentRole
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()


async def get_current_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Agent:
    """Get the current authenticated agent from API key or JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    agent = None

    # Try API key first
    if api_key:
        stmt = select(Agent).where(Agent.is_active == True)
        result = await db.execute(stmt)
        agents = result.scalars().all()

        for a in agents:
            if verify_api_key(api_key, a.api_key_hash):
                agent = a
                break

    # Try JWT token
    if not agent and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            payload = decode_access_token(token)
            if payload and "sub" in payload:
                stmt = select(Agent).where(
                    Agent.uuid == payload["sub"],
                    Agent.is_active == True,
                )
                result = await db.execute(stmt)
                agent = result.scalar_one_or_none()

    if not agent:
        raise credentials_exception

    # Update last seen
    agent.last_seen_at = request.state.get("request_time")
    await db.flush()

    return agent


async def get_admin_agent(
    current_agent: Agent = Depends(get_current_agent),
) -> Agent:
    """Require admin role."""
    if current_agent.role != AgentRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_agent


async def get_operator_agent(
    current_agent: Agent = Depends(get_current_agent),
) -> Agent:
    """Require operator role or higher."""
    if current_agent.role not in (AgentRole.ADMIN, AgentRole.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    return current_agent


def get_settings_dependency() -> Settings:
    """Get settings instance."""
    return get_settings()


class Settings:
    """Placeholder for settings dependency."""
    pass
