"""Approval queue service for human-in-the-loop decisions."""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from app.models import Agent, ApprovalRequest, ToolCall, ToolCallStatus
from app.schemas import ApprovalDecision
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class ApprovalService:
    """Manages approval requests for risky tool calls."""

    def __init__(self, db: AsyncSession, default_timeout_seconds: int = 300):
        self.db = db
        self.default_timeout = default_timeout_seconds

    async def create_approval_request(
        self,
        tool_call: ToolCall,
        agent: Agent,
        reason: str,
        expires_in_seconds: Optional[int] = None,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds or self.default_timeout)

        approval = ApprovalRequest(
            uuid=str(uuid.uuid4()),
            tool_call_id=tool_call.id,
            agent_id=agent.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            reason=reason,
            status="pending",
            expires_at=expires_at,
        )

        self.db.add(approval)
        await self.db.flush()
        await self.db.refresh(approval)

        # Update tool call status
        tool_call.status = ToolCallStatus.PENDING_APPROVAL
        tool_call.approval_id = approval.id
        await self.db.flush()

        return approval

    async def get_pending_approvals(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .where(ApprovalRequest.expires_at > datetime.utcnow())
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_approval_by_uuid(self, uuid_str: str) -> Optional[ApprovalRequest]:
        """Get approval request by UUID."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.uuid == uuid_str)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_approval_by_tool_call(self, tool_call_id: int) -> Optional[ApprovalRequest]:
        """Get approval request by tool call ID."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.tool_call_id == tool_call_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def decide_approval(
        self,
        approval: ApprovalRequest,
        decision: ApprovalDecision,
        decided_by: Agent,
    ) -> tuple[bool, Optional[ToolCall]]:
        """Process an approval decision."""
        if approval.status != "pending":
            return False, None

        if datetime.utcnow() > approval.expires_at:
            approval.status = "expired"
            await self.db.flush()
            return False, None

        # Get the associated tool call
        stmt = select(ToolCall).where(ToolCall.id == approval.tool_call_id)
        result = await self.db.execute(stmt)
        tool_call = result.scalar_one_or_none()

        if not tool_call:
            return False, None

        if decision.approve:
            approval.status = "approved"
            tool_call.status = ToolCallStatus.APPROVED
        else:
            approval.status = "denied"
            tool_call.status = ToolCallStatus.DENIED

        approval.decided_by = decided_by.id
        approval.decision_reason = decision.reason
        approval.decided_at = datetime.utcnow()
        tool_call.completed_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(tool_call)

        return True, tool_call

    async def expire_old_requests(self) -> int:
        """Expire old pending requests. Returns count of expired requests."""
        stmt = (
            update(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .where(ApprovalRequest.expires_at <= datetime.utcnow())
            .values(status="expired")
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def get_approval_stats(self) -> dict:
        """Get approval queue statistics."""
        from sqlalchemy import func

        # Pending count
        pending_stmt = select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at > datetime.utcnow(),
        )
        pending = (await self.db.execute(pending_stmt)).scalar_one()

        # Expired count
        expired_stmt = select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == "expired",
        )
        expired = (await self.db.execute(expired_stmt)).scalar_one()

        # Approved count
        approved_stmt = select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == "approved",
        )
        approved = (await self.db.execute(approved_stmt)).scalar_one()

        # Denied count
        denied_stmt = select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == "denied",
        )
        denied = (await self.db.execute(denied_stmt)).scalar_one()

        return {
            "pending": pending,
            "expired": expired,
            "approved": approved,
            "denied": denied,
        }
