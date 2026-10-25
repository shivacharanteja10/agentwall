"""Unit tests for audit logger."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from sqlalchemy import select

from app.models import ToolCall, ToolCallStatus, Agent
from app.services.audit_logger import AuditLogger
from app.core.security import hash_request, compute_chain_hash


def make_mock_result(data):
    """Create a mock result that returns data when scalars().all() is called."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = data
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    return mock_result


def make_mock_scalar_one_or_none(value):
    """Create a mock result that returns value when scalar_one_or_none() is called."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def audit_logger(mock_db):
    return AuditLogger(mock_db)


def setup_mock_db_execute(mock_db, result_data=None, scalar_value=None):
    """Setup mock_db.execute to return a proper result."""
    if scalar_value is not None:
        mock_db.execute.return_value = make_mock_scalar_one_or_none(scalar_value)
    else:
        mock_db.execute.return_value = make_mock_result(result_data or [])


class TestAuditLogger:
    """Tests for AuditLogger."""

    @pytest.mark.asyncio
    async def test_log_tool_call_first_entry(self, audit_logger, mock_db):
        """Test logging the first tool call (no previous hash)."""
        setup_mock_db_execute(mock_db, scalar_value=None)

        tool_call = await audit_logger.log_tool_call(
            agent_id=1,
            tool_name="fs_read",
            arguments={"path": "test.txt"},
            result={"content": "file content"},
            status=ToolCallStatus.ALLOWED,
        )

        assert tool_call.agent_id == 1
        assert tool_call.tool_name == "fs_read"
        assert tool_call.status == ToolCallStatus.ALLOWED
        assert tool_call.previous_hash is None
        assert tool_call.chain_hash == tool_call.request_hash

        # Verify the chain hash is correctly computed
        expected_chain = compute_chain_hash(tool_call.request_hash, None)
        assert tool_call.chain_hash == expected_chain

    @pytest.mark.asyncio
    async def test_log_tool_call_chained(self, audit_logger, mock_db):
        """Test logging subsequent tool calls with chain hash."""
        previous_hash = "abc123"
        setup_mock_db_execute(mock_db, scalar_value=previous_hash)

        tool_call = await audit_logger.log_tool_call(
            agent_id=1,
            tool_name="fs_write",
            arguments={"path": "test.txt", "content": "hello"},
            result=None,
            status=ToolCallStatus.ALLOWED,
        )

        assert tool_call.previous_hash == previous_hash
        expected_chain = compute_chain_hash(tool_call.request_hash, previous_hash)
        assert tool_call.chain_hash == expected_chain

    @pytest.mark.asyncio
    async def test_verify_chain_valid(self, audit_logger, mock_db):
        """Test chain verification with valid chain."""
        # Create mock tool calls with correct chain
        call1 = MagicMock(spec=ToolCall)
        call1.id = 1
        call1.uuid = "uuid-1"
        call1.agent_id = 1
        call1.tool_name = "fs_read"
        call1.arguments = {"path": "test.txt"}
        call1.created_at = datetime(2024, 1, 1, 12, 0, 0)
        call1.request_hash = hash_request({
            "agent_id": 1,
            "tool_name": "fs_read",
            "arguments": {"path": "test.txt"},
            "timestamp": "2024-01-01T12:00:00",
        })
        call1.previous_hash = None
        call1.chain_hash = compute_chain_hash(call1.request_hash, None)

        call2 = MagicMock(spec=ToolCall)
        call2.id = 2
        call2.uuid = "uuid-2"
        call2.agent_id = 1
        call2.tool_name = "fs_write"
        call2.arguments = {"path": "test.txt", "content": "hello"}
        call2.created_at = datetime(2024, 1, 1, 12, 0, 1)
        call2.request_hash = hash_request({
            "agent_id": 1,
            "tool_name": "fs_write",
            "arguments": {"path": "test.txt", "content": "hello"},
            "timestamp": "2024-01-01T12:00:01",
        })
        call2.previous_hash = call1.chain_hash
        call2.chain_hash = compute_chain_hash(call2.request_hash, call1.chain_hash)

        setup_mock_db_execute(mock_db, [call1, call2])

        is_valid, issues = await audit_logger.verify_chain()

        assert is_valid is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_verify_chain_invalid_request_hash(self, audit_logger, mock_db):
        """Test chain verification detects tampered request hash."""
        call1 = MagicMock(spec=ToolCall)
        call1.id = 1
        call1.uuid = "uuid-1"
        call1.agent_id = 1
        call1.tool_name = "fs_read"
        call1.arguments = {"path": "test.txt"}
        call1.created_at = datetime(2024, 1, 1, 12, 0, 0)
        call1.request_hash = "tampered_hash"  # Wrong hash
        call1.previous_hash = None
        call1.chain_hash = compute_chain_hash(call1.request_hash, None)

        setup_mock_db_execute(mock_db, [call1])

        is_valid, issues = await audit_logger.verify_chain()

        assert is_valid is False
        assert len(issues) == 1
        assert issues[0]["issue"] == "request_hash_mismatch"

    @pytest.mark.asyncio
    async def test_verify_chain_invalid_chain_hash(self, audit_logger, mock_db):
        """Test chain verification detects tampered chain hash."""
        call1 = MagicMock(spec=ToolCall)
        call1.id = 1
        call1.uuid = "uuid-1"
        call1.agent_id = 1
        call1.tool_name = "fs_read"
        call1.arguments = {"path": "test.txt"}
        call1.created_at = datetime(2024, 1, 1, 12, 0, 0)
        call1.request_hash = hash_request({
            "agent_id": 1,
            "tool_name": "fs_read",
            "arguments": {"path": "test.txt"},
            "timestamp": "2024-01-01T12:00:00",
        })
        call1.previous_hash = None
        call1.chain_hash = "tampered_chain_hash"  # Wrong chain hash

        setup_mock_db_execute(mock_db, [call1])

        is_valid, issues = await audit_logger.verify_chain()

        assert is_valid is False
        assert len(issues) == 1
        assert issues[0]["issue"] == "chain_hash_mismatch"

    @pytest.mark.asyncio
    async def test_verify_chain_invalid_previous_hash(self, audit_logger, mock_db):
        """Test chain verification detects broken previous hash link."""
        call1 = MagicMock(spec=ToolCall)
        call1.id = 1
        call1.uuid = "uuid-1"
        call1.agent_id = 1
        call1.tool_name = "fs_read"
        call1.arguments = {"path": "test.txt"}
        call1.created_at = datetime(2024, 1, 1, 12, 0, 0)
        call1.request_hash = hash_request({
            "agent_id": 1,
            "tool_name": "fs_read",
            "arguments": {"path": "test.txt"},
            "timestamp": "2024-01-01T12:00:00",
        })
        call1.previous_hash = None
        call1.chain_hash = compute_chain_hash(call1.request_hash, None)

        call2 = MagicMock(spec=ToolCall)
        call2.id = 2
        call2.uuid = "uuid-2"
        call2.agent_id = 1
        call2.tool_name = "fs_write"
        call2.arguments = {"path": "test.txt", "content": "hello"}
        call2.created_at = datetime(2024, 1, 1, 12, 0, 1)
        call2.request_hash = hash_request({
            "agent_id": 1,
            "tool_name": "fs_write",
            "arguments": {"path": "test.txt", "content": "hello"},
            "timestamp": "2024-01-01T12:00:01",
        })
        call2.previous_hash = "wrong_previous_hash"  # Doesn't match call1.chain_hash
        call2.chain_hash = compute_chain_hash(call2.request_hash, call2.previous_hash)

        setup_mock_db_execute(mock_db, [call1, call2])

        is_valid, issues = await audit_logger.verify_chain()

        assert is_valid is False
        assert any(i["issue"] == "previous_hash_mismatch" for i in issues)

    @pytest.mark.asyncio
    async def test_get_audit_trail(self, audit_logger, mock_db):
        """Test retrieving audit trail with filters."""
        mock_calls = [
            MagicMock(spec=ToolCall, id=1, tool_name="fs_read"),
            MagicMock(spec=ToolCall, id=2, tool_name="fs_write"),
        ]
        setup_mock_db_execute(mock_db, mock_calls)

        calls = await audit_logger.get_audit_trail(agent_id=1, tool_name="fs_read", limit=10)

        assert len(calls) == 2
        # Verify the query was built with filters
        mock_db.execute.assert_called()


class TestSecurityHashing:
    """Tests for security hashing functions."""

    def test_hash_request_deterministic(self):
        """Test that hashing is deterministic."""
        data = {"agent_id": 1, "tool_name": "fs_read", "arguments": {"path": "test.txt"}}
        hash1 = hash_request(data)
        hash2 = hash_request(data)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_hash_request_order_independent(self):
        """Test that hash is independent of key order."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        assert hash_request(data1) == hash_request(data2)

    def test_compute_chain_hash_first(self):
        """Test chain hash for first entry."""
        current = "abc123"
        chain = compute_chain_hash(current, None)
        assert chain == current

    def test_compute_chain_hash_chained(self):
        """Test chain hash for subsequent entries."""
        previous = "prev_hash"
        current = "curr_hash"
        chain = compute_chain_hash(current, previous)
        # Should be hash of "prev_hash:curr_hash"
        import hashlib
        expected = hashlib.sha256(f"{previous}:{current}".encode()).hexdigest()
        assert chain == expected