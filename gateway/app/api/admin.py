"""Admin API routes for agents, policies, approvals, and audit."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_admin_agent, get_db, get_operator_agent
from app.core.security import generate_api_key, hash_api_key
from app.models import (
    Agent,
    AgentRole,
    ApprovalRequest,
    Policy,
    ToolCallStatus,
    ToolServer,
)
from app.schemas import (
    AgentCreate,
    AgentResponse,
    AgentWithKey,
    ApprovalDecision,
    ApprovalRequestResponse,
    HealthResponse,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    ToolCallResponse,
    ToolResponse,
    ToolServerCreate,
    ToolServerResponse,
)
from app.services.approval_service import ApprovalService
from app.services.audit_logger import AuditLogger
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])


# Health check
@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Health check endpoint."""
    from app.services.rate_limiter import get_rate_limiter
    from app.services.upstream_client import get_upstream_manager

    # Check database
    db_status = "healthy"
    try:
        await db.execute(select(1))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    redis_status = "healthy"
    rate_limiter = await get_rate_limiter()
    if not rate_limiter._enabled:
        redis_status = "unhealthy"

    # Check upstream servers
    upstream = get_upstream_manager()
    upstream_healthy = 0
    for name in upstream.get_registered_servers():
        config = upstream._configs[name]
        from app.services.upstream_client import UpstreamClient
        async with UpstreamClient(config) as client:
            if await client.health_check():
                upstream_healthy += 1

    return HealthResponse(
        status="healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        version="0.1.0",
        database=db_status,
        redis=redis_status,
        timestamp=datetime.utcnow(),
    )


# Agent management
@router.post("/agents", response_model=AgentWithKey, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> AgentWithKey:
    """Create a new agent with API key."""
    # Check if name exists
    stmt = select(Agent).where(Agent.name == agent_data.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent name already exists")

    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    agent = Agent(
        name=agent_data.name,
        role=agent_data.role,
        api_key_hash=api_key_hash,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentWithKey(
        id=agent.id,
        uuid=agent.uuid,
        name=agent.name,
        role=agent.role,
        is_active=agent.is_active,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        last_seen_at=agent.last_seen_at,
        api_key=api_key,
    )


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[AgentResponse]:
    """List all agents."""
    stmt = select(Agent).order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> AgentResponse:
    """Get agent by ID."""
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> None:
    """Delete an agent."""
    if agent_id == current_agent.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()


# Tool Server management
@router.post("/tool-servers", response_model=ToolServerResponse, status_code=status.HTTP_201_CREATED)
async def create_tool_server(
    server_data: ToolServerCreate,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> ToolServerResponse:
    """Register a new upstream tool server."""
    stmt = select(ToolServer).where(ToolServer.name == server_data.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Tool server name already exists")

    server = ToolServer(**server_data.model_dump())
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return ToolServerResponse.model_validate(server)


@router.get("/tool-servers", response_model=list[ToolServerResponse])
async def list_tool_servers(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> list[ToolServerResponse]:
    """List all registered tool servers."""
    stmt = select(ToolServer).order_by(ToolServer.created_at.desc())
    result = await db.execute(stmt)
    return [ToolServerResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/tool-servers/{server_id}/sync", status_code=status.HTTP_200_OK)
async def sync_tool_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> dict:
    """Sync tools from an upstream server."""
    from app.services.upstream_client import UpstreamClient, UpstreamServerConfig

    stmt = select(ToolServer).where(ToolServer.id == server_id)
    result = await db.execute(stmt)
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Tool server not found")

    config = UpstreamServerConfig(name=server.name, base_url=server.base_url)
    async with UpstreamClient(config) as client:
        tools = await client.list_tools()

    # Upsert tools
    synced = 0
    for tool_def in tools:
        stmt = select(Tool).where(Tool.server_id == server_id, Tool.name == tool_def.name)
        result = await db.execute(stmt)
        tool = result.scalar_one_or_none()

        if tool:
            tool.description = tool_def.description
            tool.input_schema = tool_def.inputSchema
            tool.output_schema = tool_def.outputSchema or {}
            tool.is_active = True
        else:
            tool = Tool(
                server_id=server_id,
                name=tool_def.name,
                description=tool_def.description,
                input_schema=tool_def.inputSchema,
                output_schema=tool_def.outputSchema or {},
            )
            db.add(tool)
        synced += 1

    await db.commit()
    return {"synced": synced, "tools": [t.name for t in tools]}


# Tool management
@router.get("/tools", response_model=list[ToolResponse])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
    server_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
) -> list[ToolResponse]:
    """List all tools."""
    stmt = select(Tool)
    if server_id:
        stmt = stmt.where(Tool.server_id == server_id)
    if active_only:
        stmt = stmt.where(Tool.is_active == True)
    stmt = stmt.order_by(Tool.name)
    result = await db.execute(stmt)
    return [ToolResponse.model_validate(t) for t in result.scalars().all()]


# Policy management
@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> PolicyResponse:
    """Create a new policy."""
    stmt = select(Policy).where(Policy.name == policy_data.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Policy name already exists")

    policy = Policy(**policy_data.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
    role: Optional[AgentRole] = Query(None),
    active_only: bool = Query(True),
) -> list[PolicyResponse]:
    """List all policies."""
    stmt = select(Policy).order_by(Policy.priority.desc(), Policy.id)
    if role:
        stmt = stmt.where(Policy.role == role)
    if active_only:
        stmt = stmt.where(Policy.is_active == True)
    result = await db.execute(stmt)
    return [PolicyResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> PolicyResponse:
    """Get policy by ID."""
    stmt = select(Policy).where(Policy.id == policy_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyResponse.model_validate(policy)


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    policy_update: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> PolicyResponse:
    """Update a policy."""
    stmt = select(Policy).where(Policy.id == policy_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    update_data = policy_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
) -> None:
    """Delete a policy."""
    stmt = select(Policy).where(Policy.id == policy_id)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.commit()


# Approval queue
@router.get("/approvals", response_model=list[ApprovalRequestResponse])
async def list_approvals(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[ApprovalRequestResponse]:
    """List approval requests."""
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [ApprovalRequestResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/approvals/{approval_uuid}", response_model=ApprovalRequestResponse)
async def get_approval(
    approval_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> ApprovalRequestResponse:
    """Get approval request by UUID."""
    stmt = select(ApprovalRequest).where(ApprovalRequest.uuid == str(approval_uuid))
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return ApprovalRequestResponse.model_validate(approval)


@router.post("/approvals/{approval_uuid}/decide", response_model=ApprovalRequestResponse)
async def decide_approval(
    approval_uuid: UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> ApprovalRequestResponse:
    """Approve or deny an approval request."""
    approval_service = ApprovalService(db)

    stmt = select(ApprovalRequest).where(ApprovalRequest.uuid == str(approval_uuid))
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    success, tool_call = await approval_service.decide_approval(approval, decision, current_agent)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot process approval (expired or already decided)")

    await db.commit()
    await db.refresh(approval)
    return ApprovalRequestResponse.model_validate(approval)


# Audit log
@router.get("/audit", response_model=list[ToolCallResponse])
async def list_audit(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
    agent_id: Optional[int] = Query(None),
    tool_name: Optional[str] = Query(None),
    status_filter: Optional[ToolCallStatus] = Query(None, alias="status"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[ToolCallResponse]:
    """List audit log entries."""
    audit_logger = AuditLogger(db)
    calls = await audit_logger.get_audit_trail(
        agent_id=agent_id,
        tool_name=tool_name,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [ToolCallResponse.model_validate(c) for c in calls]


@router.get("/audit/stats")
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> dict:
    """Get audit statistics."""
    audit_logger = AuditLogger(db)
    return await audit_logger.get_stats()


@router.post("/audit/verify")
async def verify_audit_chain(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_admin_agent),
    limit: Optional[int] = Query(None),
) -> dict:
    """Verify the integrity of the audit chain."""
    audit_logger = AuditLogger(db)
    is_valid, issues = await audit_logger.verify_chain(limit=limit)
    return {
        "valid": is_valid,
        "issues_count": len(issues),
        "issues": issues[:50],  # Limit response size
    }


# Approval stats
@router.get("/approvals/stats")
async def get_approval_stats(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_operator_agent),
) -> dict:
    """Get approval queue statistics."""
    approval_service = ApprovalService(db)
    return await approval_service.get_approval_stats()
