"""Pytest configuration and fixtures."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AgentRole


@pytest.fixture
def mock_async_session():
    """Mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def sample_agent():
    """Sample agent for testing."""
    return Agent(
        id=1,
        uuid="123e4567-e89b-12d3-a456-426614174000",
        name="test-agent",
        role=AgentRole.OPERATOR,
        api_key_hash="hashed_key",
        is_active=True,
    )


@pytest.fixture
def sample_admin_agent():
    """Sample admin agent for testing."""
    return Agent(
        id=2,
        uuid="123e4567-e89b-12d3-a456-426614174001",
        name="admin-agent",
        role=AgentRole.ADMIN,
        api_key_hash="hashed_key",
        is_active=True,
    )


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset global service instances
    import app.services.rate_limiter as rl
    import app.services.threat_detection as td
    import app.services.upstream_client as uc

    rl._rate_limiter = None
    rl._egress_controller = None
    rl._loop_detector = None
    td._prompt_detector = None
    td._dlp = None
    uc._upstream_manager = None

    yield

    # Cleanup after test
    rl._rate_limiter = None
    rl._egress_controller = None
    rl._loop_detector = None
    td._prompt_detector = None
    td._dlp = None
    uc._upstream_manager = None