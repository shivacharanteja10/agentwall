"""Unit tests for the policy engine."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models import Agent, AgentRole, Policy, ToolCallStatus
from app.schemas import ToolCallRequest
from app.services.policy_engine import PolicyEngine, validate_arguments_against_schema


def make_mock_result(policies):
    """Create a mock result that returns policies when scalars().all() is called."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = policies
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def setup_mock_db(mock_db, policies):
    """Setup mock_db.execute to return policies."""
    mock_result = make_mock_result(policies)
    mock_db.execute.return_value = mock_result


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def agent_admin():
    return Agent(
        id=1,
        uuid="123e4567-e89b-12d3-a456-426614174000",
        name="admin-agent",
        role=AgentRole.ADMIN,
        api_key_hash="hashed",
        is_active=True,
    )


@pytest.fixture
def agent_operator():
    return Agent(
        id=2,
        uuid="123e4567-e89b-12d3-a456-426614174001",
        name="operator-agent",
        role=AgentRole.OPERATOR,
        api_key_hash="hashed",
        is_active=True,
    )


@pytest.fixture
def agent_viewer():
    return Agent(
        id=3,
        uuid="123e4567-e89b-12d3-a456-426614174002",
        name="viewer-agent",
        role=AgentRole.VIEWER,
        api_key_hash="hashed",
        is_active=True,
    )


@pytest.fixture
def tool_call():
    return ToolCallRequest(name="fs_read", arguments={"path": "test.txt"})


@pytest.fixture
def tool_schema():
    return {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    }


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    @pytest.mark.asyncio
    async def test_default_deny(self, mock_db, agent_viewer, tool_call, tool_schema):
        """Test that default policy is deny when no policies match."""
        setup_mock_db(mock_db, [])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_viewer, tool_call, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED
        assert "Default deny" in decision.reason

    @pytest.mark.asyncio
    async def test_allow_policy(self, mock_db, agent_operator, tool_call, tool_schema):
        """Test that allow policy permits the call."""
        policy = Policy(
            id=1,
            name="allow-read",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="allow",
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_operator, tool_call, tool_schema)

        assert decision.allowed is True
        assert decision.status == ToolCallStatus.ALLOWED
        assert decision.policy_id == 1

    @pytest.mark.asyncio
    async def test_deny_policy(self, mock_db, agent_operator, tool_call, tool_schema):
        """Test that deny policy blocks the call."""
        policy = Policy(
            id=2,
            name="deny-read",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="deny",
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_operator, tool_call, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED
        assert decision.policy_id == 2

    @pytest.mark.asyncio
    async def test_require_approval_policy(self, mock_db, agent_operator, tool_call, tool_schema):
        """Test that require_approval policy sets pending status."""
        policy = Policy(
            id=3,
            name="approval-read",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="require_approval",
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_operator, tool_call, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.PENDING_APPROVAL
        assert decision.requires_approval is True
        assert decision.policy_id == 3

    @pytest.mark.asyncio
    async def test_priority_ordering(self, mock_db, agent_operator, tool_call, tool_schema):
        """Test that higher priority policies are evaluated first."""
        deny_policy = Policy(
            id=1,
            name="deny-low-priority",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="deny",
            is_active=True,
            priority=5,
        )
        allow_policy = Policy(
            id=2,
            name="allow-high-priority",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="allow",
            is_active=True,
            priority=10,
        )
        # Engine orders by priority desc, so allow_policy (10) comes first in mock
        setup_mock_db(mock_db, [allow_policy, deny_policy])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_operator, tool_call, tool_schema)

        # Higher priority (allow) should win
        assert decision.allowed is True
        assert decision.policy_id == 2

    @pytest.mark.asyncio
    async def test_role_mismatch(self, mock_db, agent_viewer, tool_call, tool_schema):
        """Test that policies for different roles don't apply."""
        # Engine filters by role in SQL, so mock should return empty for viewer agent
        setup_mock_db(mock_db, [])

        engine = PolicyEngine(mock_db)
        decision = await engine.evaluate(agent_viewer, tool_call, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED

    @pytest.mark.asyncio
    async def test_tool_name_filter(self, mock_db, agent_operator, tool_schema):
        """Test that tool_name filter works."""
        policy = Policy(
            id=1,
            name="write-only",
            role=AgentRole.OPERATOR,
            tool_name="fs_write",
            action="allow",
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        # Call fs_read, but policy is for fs_write
        tool_call_read = ToolCallRequest(name="fs_read", arguments={"path": "test.txt"})
        decision = await engine.evaluate(agent_operator, tool_call_read, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED

    @pytest.mark.asyncio
    async def test_argument_pattern_match(self, mock_db, agent_operator, tool_schema):
        """Test argument pattern matching with regex."""
        policy = Policy(
            id=1,
            name="secret-path-deny",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="deny",
            argument_pattern={"path": ".*secret.*"},
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        # This should match the pattern
        tool_call_secret = ToolCallRequest(name="fs_read", arguments={"path": "secret.txt"})
        decision = await engine.evaluate(agent_operator, tool_call_secret, tool_schema)

        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED

    @pytest.mark.asyncio
    async def test_argument_pattern_no_match(self, mock_db, agent_operator, tool_schema):
        """Test argument pattern that doesn't match."""
        policy = Policy(
            id=1,
            name="secret-path-deny",
            role=AgentRole.OPERATOR,
            tool_name="fs_read",
            action="deny",
            argument_pattern={"path": ".*secret.*"},
            is_active=True,
            priority=10,
        )
        setup_mock_db(mock_db, [policy])

        engine = PolicyEngine(mock_db)
        # This should NOT match the pattern, so deny policy is skipped
        # Falls through to default deny
        tool_call_normal = ToolCallRequest(name="fs_read", arguments={"path": "normal.txt"})
        decision = await engine.evaluate(agent_operator, tool_call_normal, tool_schema)

        # Default deny applies since no allow policy matches
        assert decision.allowed is False
        assert decision.status == ToolCallStatus.DENIED


class TestArgumentValidation:
    """Tests for argument schema validation."""

    @pytest.mark.asyncio
    async def test_valid_arguments(self):
        """Test valid arguments pass validation."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["path"],
        }
        args = {"path": "test.txt", "count": 5}
        valid, error = await validate_arguments_against_schema(args, schema)
        assert valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_missing_required(self):
        """Test missing required field fails."""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        args = {"count": 5}
        valid, error = await validate_arguments_against_schema(args, schema)
        assert valid is False
        assert "Missing required field: path" in error

    @pytest.mark.asyncio
    async def test_wrong_type(self):
        """Test wrong type fails."""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        args = {"path": 123}
        valid, error = await validate_arguments_against_schema(args, schema)
        assert valid is False
        assert "expected type string" in error

    @pytest.mark.asyncio
    async def test_extra_fields_allowed(self):
        """Test extra fields are allowed (not strict)."""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        args = {"path": "test.txt", "extra": "field"}
        valid, error = await validate_arguments_against_schema(args, schema)
        assert valid is True