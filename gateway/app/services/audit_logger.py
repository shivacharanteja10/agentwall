"""Audit logging with tamper-evident hash chaining."""
from datetime import datetime
from typing import Optional

from app.core.security import compute_chain_hash, hash_request
from app.models import ToolCall, ToolCallStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditLogger:
    """Tamper-evident audit logger with hash chaining."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_tool_call(
        self,
        agent_id: Optional[int],
        tool_name: str,
        arguments: dict,
        result: Optional[dict],
        status: ToolCallStatus,
        policy_id: Optional[int] = None,
        approval_id: Optional[int] = None,
        threat_detected: bool = False,
        threat_details: Optional[dict] = None,
        dlp_redacted: bool = False,
        dlp_details: Optional[dict] = None,
    ) -> ToolCall:
        """Log a tool call with hash chaining."""
        # Create request data for hashing
        request_data = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "timestamp": datetime.utcnow().isoformat(),
        }
        request_hash = hash_request(request_data)

        # Get the previous chain hash
        previous_hash = await self._get_last_chain_hash()

        # Compute chained hash
        chain_hash = compute_chain_hash(request_hash, previous_hash)

        # Create audit record
        tool_call = ToolCall(
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            status=status,
            policy_id=policy_id,
            approval_id=approval_id,
            threat_detected=threat_detected,
            threat_details=threat_details,
            dlp_redacted=dlp_redacted,
            dlp_details=dlp_details,
            request_hash=request_hash,
            previous_hash=previous_hash,
            chain_hash=chain_hash,
            completed_at=datetime.utcnow() if status in (
                ToolCallStatus.ALLOWED, ToolCallStatus.DENIED, ToolCallStatus.REDACTED
            ) else None,
        )

        self.db.add(tool_call)
        await self.db.flush()
        await self.db.refresh(tool_call)

        return tool_call

    async def update_tool_call_result(
        self,
        tool_call_id: int,
        result: dict,
        status: ToolCallStatus,
    ) -> Optional[ToolCall]:
        """Update a tool call with its result and final status."""
        stmt = select(ToolCall).where(ToolCall.id == tool_call_id)
        result_obj = await self.db.execute(stmt)
        tool_call = result_obj.scalar_one_or_none()

        if tool_call:
            tool_call.result = result
            tool_call.status = status
            tool_call.completed_at = datetime.utcnow()
            await self.db.flush()
            await self.db.refresh(tool_call)

        return tool_call

    async def _get_last_chain_hash(self) -> Optional[str]:
        """Get the chain_hash of the most recent audit entry."""
        stmt = select(ToolCall.chain_hash).order_by(ToolCall.id.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def verify_chain(self, limit: Optional[int] = None) -> tuple[bool, list[dict]]:
        """
        Verify the integrity of the audit chain.
        Returns (is_valid, list_of_issues).
        """
        stmt = select(ToolCall).order_by(ToolCall.id)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        calls = result.scalars().all()

        issues = []
        previous_hash = None

        for i, call in enumerate(calls):
            # Recompute request hash
            request_data = {
                "agent_id": call.agent_id,
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "timestamp": call.created_at.isoformat() if call.created_at else "",
            }
            expected_request_hash = hash_request(request_data)

            if call.request_hash != expected_request_hash:
                issues.append({
                    "index": i,
                    "tool_call_id": call.id,
                    "uuid": str(call.uuid),
                    "issue": "request_hash_mismatch",
                    "expected": expected_request_hash,
                    "actual": call.request_hash,
                })

            # Recompute chain hash
            expected_chain_hash = compute_chain_hash(call.request_hash, previous_hash)

            if call.chain_hash != expected_chain_hash:
                issues.append({
                    "index": i,
                    "tool_call_id": call.id,
                    "uuid": str(call.uuid),
                    "issue": "chain_hash_mismatch",
                    "expected": expected_chain_hash,
                    "actual": call.chain_hash,
                    "previous_hash": previous_hash,
                })

            # Verify previous_hash matches previous entry's chain_hash
            if call.previous_hash != previous_hash:
                issues.append({
                    "index": i,
                    "tool_call_id": call.id,
                    "uuid": str(call.uuid),
                    "issue": "previous_hash_mismatch",
                    "expected": previous_hash,
                    "actual": call.previous_hash,
                })

            previous_hash = call.chain_hash

        return len(issues) == 0, issues

    async def get_audit_trail(
        self,
        agent_id: Optional[int] = None,
        tool_name: Optional[str] = None,
        status: Optional[ToolCallStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCall]:
        """Retrieve audit trail with filters."""
        stmt = select(ToolCall).order_by(ToolCall.created_at.desc())

        if agent_id:
            stmt = stmt.where(ToolCall.agent_id == agent_id)
        if tool_name:
            stmt = stmt.where(ToolCall.tool_name == tool_name)
        if status:
            stmt = stmt.where(ToolCall.status == status)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_stats(self) -> dict:
        """Get audit statistics."""
        # Total calls
        total_stmt = select(func.count(ToolCall.id))
        total = (await self.db.execute(total_stmt)).scalar_one()

        # By status
        status_stmt = select(ToolCall.status, func.count(ToolCall.id)).group_by(ToolCall.status)
        status_result = await self.db.execute(status_stmt)
        by_status = {status.value: count for status, count in status_result.all()}

        # Threat detected count
        threat_stmt = select(func.count(ToolCall.id)).where(ToolCall.threat_detected == True)
        threats = (await self.db.execute(threat_stmt)).scalar_one()

        # DLP redacted count
        dlp_stmt = select(func.count(ToolCall.id)).where(ToolCall.dlp_redacted == True)
        dlp_count = (await self.db.execute(dlp_stmt)).scalar_one()

        return {
            "total_calls": total,
            "by_status": by_status,
            "threats_detected": threats,
            "dlp_redactions": dlp_count,
        }
