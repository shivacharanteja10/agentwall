"""Database models for AgentWall."""
import enum
from datetime import datetime
from typing import Optional

from app.db.base import Base
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AgentRole(str, enum.Enum):
    """Agent roles for RBAC."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    AUTOMATED = "automated"


class ToolCallStatus(str, enum.Enum):
    """Status of a tool call."""
    ALLOWED = "allowed"
    DENIED = "denied"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REDACTED = "redacted"
    ERROR = "error"


class Agent(Base):
    """Agent identity and authentication."""
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole), nullable=False, default=AgentRole.VIEWER)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="agent", lazy="selectin")


class ToolServer(Base):
    """Registered upstream tool servers."""
    __tablename__ = "tool_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tools: Mapped[list["Tool"]] = relationship(back_populates="server", lazy="selectin", cascade="all, delete-orphan")


class Tool(Base):
    """Tool definitions from upstream servers."""
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tool_servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    server: Mapped["ToolServer"] = relationship(back_populates="tools", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("server_id", "name", name="uq_tool_server_name"),
        Index("ix_tool_name_active", "name", "is_active"),
    )


class Policy(Base):
    """Policy rules for tool access control."""
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # allow, deny, require_approval
    argument_pattern: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    time_window_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    time_window_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_policy_role_tool_active", "role", "tool_name", "is_active"),
    )


class ToolCall(Base):
    """Audit log of tool calls."""
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[ToolCallStatus] = mapped_column(Enum(ToolCallStatus), nullable=False, index=True)
    policy_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True
    )
    approval_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    threat_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    threat_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dlp_redacted: Mapped[bool] = mapped_column(default=False, nullable=False)
    dlp_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 of request
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Chained hash
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="tool_calls", lazy="selectin")

    __table_args__ = (
        Index("ix_tool_call_agent_created", "agent_id", "created_at"),
        Index("ix_tool_call_status_created", "status", "created_at"),
    )


class ApprovalRequest(Base):
    """Human approval requests for risky actions."""
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, nullable=False, index=True)
    tool_call_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, approved, denied, expired
    requested_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_approval_status_expires", "status", "expires_at"),
    )
