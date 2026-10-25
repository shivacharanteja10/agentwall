"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.models import AgentRole, ToolCallStatus
from pydantic import BaseModel, ConfigDict, Field


# JSON-RPC 2.0 Schemas
class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict[str, Any]] = None
    id: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None
    id: Optional[Any] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""
    code: int
    message: str
    data: Optional[Any] = None


# MCP-style Tool Schemas
class ToolDefinition(BaseModel):
    """Tool definition as returned by tools/list."""
    name: str
    description: Optional[str] = None
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: Optional[dict[str, Any]] = None


class ToolsListResponse(BaseModel):
    """Response for tools/list."""
    tools: list[ToolDefinition]


class ToolCallRequest(BaseModel):
    """Request for tools/call."""
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    """Result of a tool call."""
    content: list[dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
    structuredContent: Optional[dict[str, Any]] = None


# Agent Schemas
class AgentCreate(BaseModel):
    """Schema for creating an agent."""
    name: str = Field(..., min_length=1, max_length=255)
    role: AgentRole = AgentRole.VIEWER


class AgentResponse(BaseModel):
    """Schema for agent response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    name: str
    role: AgentRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None


class AgentWithKey(AgentResponse):
    """Agent response including API key (only on creation)."""
    api_key: str


# Tool Server Schemas
class ToolServerCreate(BaseModel):
    """Schema for creating a tool server."""
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., max_length=500)
    description: Optional[str] = None


class ToolServerResponse(BaseModel):
    """Schema for tool server response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Tool Schemas
class ToolResponse(BaseModel):
    """Schema for tool response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    name: str
    description: Optional[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Policy Schemas
class PolicyCreate(BaseModel):
    """Schema for creating a policy."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    role: AgentRole
    tool_name: Optional[str] = None
    action: str = Field(..., pattern="^(allow|deny|require_approval)$")
    argument_pattern: Optional[dict[str, Any]] = None
    time_window_start: Optional[str] = Field(None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    time_window_end: Optional[str] = Field(None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    priority: int = 0


class PolicyUpdate(BaseModel):
    """Schema for updating a policy."""
    description: Optional[str] = None
    action: Optional[str] = Field(None, pattern="^(allow|deny|require_approval)$")
    argument_pattern: Optional[dict[str, Any]] = None
    time_window_start: Optional[str] = Field(None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    time_window_end: Optional[str] = Field(None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    """Schema for policy response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    role: AgentRole
    tool_name: Optional[str]
    action: str
    argument_pattern: Optional[dict[str, Any]]
    time_window_start: Optional[str]
    time_window_end: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Tool Call Schemas
class ToolCallResponse(BaseModel):
    """Schema for tool call response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    agent_id: Optional[int]
    tool_name: str
    arguments: dict[str, Any]
    result: Optional[dict[str, Any]]
    status: ToolCallStatus
    policy_id: Optional[int]
    approval_id: Optional[int]
    threat_detected: bool
    threat_details: Optional[dict[str, Any]]
    dlp_redacted: bool
    dlp_details: Optional[dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]


# Approval Schemas
class ApprovalRequestCreate(BaseModel):
    """Schema for creating an approval request."""
    tool_call_id: int
    reason: str = Field(..., min_length=1)
    expires_in_seconds: int = Field(default=300, ge=1, le=86400)


class ApprovalDecision(BaseModel):
    """Schema for approval decision."""
    approve: bool
    reason: Optional[str] = None


class ApprovalRequestResponse(BaseModel):
    """Schema for approval request response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    tool_call_id: int
    agent_id: Optional[int]
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    status: str
    expires_at: datetime
    created_at: datetime
    decided_at: Optional[datetime]
    decided_by: Optional[int]
    decision_reason: Optional[str]


# Health Check
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    redis: str
    timestamp: datetime
