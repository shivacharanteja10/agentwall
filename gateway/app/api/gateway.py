"""Main gateway API routes for JSON-RPC tool calls."""
from typing import Any

from app.api.dependencies import get_current_agent, get_db
from app.models import Agent, Tool, ToolCallStatus
from app.schemas import (
    JSONRPCRequest,
    JSONRPCResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolsListResponse,
)
from app.services.approval_service import ApprovalService
from app.services.audit_logger import AuditLogger
from app.services.policy_engine import PolicyEngine, validate_arguments_against_schema
from app.services.rate_limiter import get_egress_controller, get_loop_detector, get_rate_limiter
from app.services.threat_detection import get_dlp, get_prompt_detector
from app.services.upstream_client import get_upstream_manager
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/rpc", response_model=JSONRPCResponse)
async def handle_json_rpc(
    request: JSONRPCRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
) -> JSONRPCResponse:
    """Handle JSON-RPC 2.0 requests for MCP-style tool calls."""
    request_id = request.id

    # Route to appropriate handler based on method
    if request.method == "tools/list":
        return await _handle_tools_list(request_id, db, current_agent)
    elif request.method == "tools/call":
        return await _handle_tool_call(request, http_request, db, current_agent)
    else:
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32601, "message": f"Method not found: {request.method}"},
        )


async def _handle_tools_list(
    request_id: Any,
    db: AsyncSession,
    current_agent: Agent,
) -> JSONRPCResponse:
    """Handle tools/list request."""
    # Get tools from upstream manager
    upstream = get_upstream_manager()
    tools = await upstream.list_all_tools()

    # Filter tools based on agent's policies (optional - for now return all)
    tool_defs = [
        {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
        for t in tools
    ]

    return JSONRPCResponse(
        jsonrpc="2.0",
        id=request_id,
        result={"tools": tool_defs},
    )


async def _handle_tool_call(
    request: JSONRPCRequest,
    http_request: Request,
    db: AsyncSession,
    current_agent: Agent,
) -> JSONRPCResponse:
    """Handle tools/call request with full security pipeline."""
    request_id = request.id
    params = request.params or {}

    # Parse tool call request
    try:
        tool_call_req = ToolCallRequest(**params)
    except Exception as e:
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32602, "message": f"Invalid params: {str(e)}"},
        )

    # Initialize services
    policy_engine = PolicyEngine(db)
    audit_logger = AuditLogger(db)
    approval_service = ApprovalService(db)
    prompt_detector = get_prompt_detector()
    dlp = get_dlp()
    rate_limiter = await get_rate_limiter()
    egress_controller = await get_egress_controller()
    loop_detector = await get_loop_detector()
    upstream = get_upstream_manager()

    # Rate limiting
    agent_identifier = f"agent:{current_agent.uuid}"
    allowed, rate_info = await rate_limiter.check_rate_limit(
        agent_identifier,
        max_requests=100,
        window_seconds=60,
    )
    if not allowed:
        await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.DENIED,
            threat_detected=False,
        )
        await db.commit()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32603, "message": "Rate limit exceeded"},
        )

    # Loop detection
    suspicious, loop_info = await loop_detector.record_call(str(current_agent.uuid), tool_call_req.name)
    if suspicious:
        await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.DENIED,
            threat_detected=True,
            threat_details={"type": "loop_detection", "details": loop_info},
        )
        await db.commit()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32603, "message": "Loop detected: suspicious call pattern"},
        )

    # Get tool definition for schema validation
    tool_stmt = select(Tool).where(Tool.name == tool_call_req.name, Tool.is_active == True)
    tool_result = await db.execute(tool_stmt)
    tool = tool_result.scalar_one_or_none()

    if not tool:
        await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.DENIED,
            threat_detected=False,
        )
        await db.commit()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32601, "message": f"Tool not found: {tool_call_req.name}"},
        )

    # Validate arguments against schema
    valid, validation_error = await validate_arguments_against_schema(
        tool_call_req.arguments,
        tool.input_schema,
    )
    if not valid:
        await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.DENIED,
            threat_detected=False,
        )
        await db.commit()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32602, "message": validation_error},
        )

    # Threat detection on input
    input_text = str(tool_call_req.arguments)
    threat_result = prompt_detector.detect(input_text, context="input")

    # Policy evaluation
    policy_decision = await policy_engine.evaluate(current_agent, tool_call_req, tool.input_schema)

    # Handle policy decision
    if policy_decision.status == ToolCallStatus.DENIED:
        await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.DENIED,
            policy_id=policy_decision.policy_id,
            threat_detected=threat_result.detected,
            threat_details=threat_result.details if threat_result.detected else None,
        )
        await db.commit()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32603, "message": policy_decision.reason},
        )

    if policy_decision.status == ToolCallStatus.PENDING_APPROVAL:
        # Create approval request
        approval = await approval_service.create_approval_request(
            tool_call=None,  # Will be set after audit log
            agent=current_agent,
            reason=policy_decision.reason,
        )
        # We need to create a provisional tool call first
        tool_call = await audit_logger.log_tool_call(
            agent_id=current_agent.id,
            tool_name=tool_call_req.name,
            arguments=tool_call_req.arguments,
            result=None,
            status=ToolCallStatus.PENDING_APPROVAL,
            policy_id=policy_decision.policy_id,
            approval_id=approval.id,
            threat_detected=threat_result.detected,
            threat_details=threat_result.details if threat_result.detected else None,
        )
        # Update approval with tool_call_id
        approval.tool_call_id = tool_call.id
        await db.commit()

        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            result={
                "content": [{"type": "text", "text": "Request pending approval"}],
                "isError": False,
                "structuredContent": {
                    "status": "pending_approval",
                    "approval_id": str(approval.uuid),
                    "expires_at": approval.expires_at.isoformat(),
                },
            },
        )

    # Policy allows - proceed with tool call
    # Call upstream tool
    tool_result = await upstream.call_tool(tool_call_req.name, tool_call_req.arguments)

    # Threat detection on output
    output_text = str(tool_result.content) if tool_result.content else ""
    output_threat = prompt_detector.detect(output_text, context="output")

    # DLP scanning on output
    dlp_redacted = False
    dlp_details = None
    redacted_result = tool_result

    if tool_result.structuredContent:
        found, findings, redacted_content = dlp.scan_dict(tool_result.structuredContent)
        if found:
            dlp_redacted = True
            dlp_details = {"findings": findings}
            redacted_result = ToolCallResult(
                content=tool_result.content,
                isError=tool_result.isError,
                structuredContent=redacted_content,
            )

    # Also scan content array
    for item in tool_result.content:
        if item.get("type") == "text":
            found, findings, redacted_text = dlp.scan(item.get("text", ""))
            if found:
                dlp_redacted = True
                if not dlp_details:
                    dlp_details = {"findings": []}
                dlp_details["findings"].extend(findings)
                item["text"] = redacted_text

    # Combine threat results
    combined_threat = threat_result.detected or output_threat.detected
    combined_threat_details = {}
    if threat_result.detected:
        combined_threat_details["input"] = threat_result.details
    if output_threat.detected:
        combined_threat_details["output"] = output_threat.details

    # Determine final status
    final_status = ToolCallStatus.ALLOWED
    if combined_threat:
        final_status = ToolCallStatus.DENIED
    elif dlp_redacted:
        final_status = ToolCallStatus.REDACTED

    # Log the tool call
    await audit_logger.log_tool_call(
        agent_id=current_agent.id,
        tool_name=tool_call_req.name,
        arguments=tool_call_req.arguments,
        result=redacted_result.model_dump() if redacted_result else None,
        status=final_status,
        policy_id=policy_decision.policy_id,
        threat_detected=combined_threat,
        threat_details=combined_threat_details if combined_threat else None,
        dlp_redacted=dlp_redacted,
        dlp_details=dlp_details,
    )
    await db.commit()

    # Return result
    if final_status == ToolCallStatus.DENIED and combined_threat:
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request_id,
            error={"code": -32603, "message": "Request blocked: threat detected"},
        )

    return JSONRPCResponse(
        jsonrpc="2.0",
        id=request_id,
        result=redacted_result.model_dump(exclude_none=True),
    )


@router.get("/tools", response_model=ToolsListResponse)
async def list_tools_http(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
) -> ToolsListResponse:
    """HTTP endpoint for listing tools (alternative to JSON-RPC)."""
    upstream = get_upstream_manager()
    tools = await upstream.list_all_tools()
    return ToolsListResponse(tools=tools)
