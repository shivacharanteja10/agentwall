"""Policy engine for evaluating tool call permissions."""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models import Agent, Policy, ToolCallStatus
from app.schemas import ToolCallRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    allowed: bool
    status: ToolCallStatus
    policy_id: Optional[int]
    reason: str
    requires_approval: bool = False


class PolicyEngine:
    """Evaluates policies against tool calls."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate(
        self,
        agent: Agent,
        tool_call: ToolCallRequest,
        tool_input_schema: dict,
    ) -> PolicyDecision:
        """Evaluate all applicable policies for a tool call."""
        # Get all active policies for the agent's role, ordered by priority (highest first)
        stmt = (
            select(Policy)
            .where(
                Policy.role == agent.role,
                Policy.is_active == True,
            )
            .order_by(Policy.priority.desc(), Policy.id)
        )
        result = await self.db.execute(stmt)
        policies = result.scalars().all()

        # Default deny
        default_decision = PolicyDecision(
            allowed=False,
            status=ToolCallStatus.DENIED,
            policy_id=None,
            reason="Default deny: no matching allow policy",
        )

        for policy in policies:
            if self._policy_matches(policy, tool_call, tool_input_schema):
                if policy.action == "allow":
                    return PolicyDecision(
                        allowed=True,
                        status=ToolCallStatus.ALLOWED,
                        policy_id=policy.id,
                        reason=f"Allowed by policy: {policy.name}",
                    )
                elif policy.action == "deny":
                    return PolicyDecision(
                        allowed=False,
                        status=ToolCallStatus.DENIED,
                        policy_id=policy.id,
                        reason=f"Denied by policy: {policy.name}",
                    )
                elif policy.action == "require_approval":
                    return PolicyDecision(
                        allowed=False,
                        status=ToolCallStatus.PENDING_APPROVAL,
                        policy_id=policy.id,
                        reason=f"Requires approval per policy: {policy.name}",
                        requires_approval=True,
                    )

        return default_decision

    def _policy_matches(
        self,
        policy: Policy,
        tool_call: ToolCallRequest,
        tool_input_schema: dict,
    ) -> bool:
        """Check if a policy matches the given tool call."""
        # Check tool name
        if policy.tool_name and policy.tool_name != tool_call.name:
            return False

        # Check time window
        if not self._in_time_window(policy):
            return False

        # Check argument pattern
        if policy.argument_pattern:
            if not self._match_arguments(policy.argument_pattern, tool_call.arguments):
                return False

        return True

    def _in_time_window(self, policy: Policy) -> bool:
        """Check if current time is within policy's time window."""
        if not policy.time_window_start and not policy.time_window_end:
            return True

        now = datetime.now().time()
        start = policy.time_window_start
        end = policy.time_window_end

        if start and end:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
            if start_time <= end_time:
                return start_time <= now <= end_time
            else:  # Overnight window
                return now >= start_time or now <= end_time
        elif start:
            start_time = datetime.strptime(start, "%H:%M").time()
            return now >= start_time
        elif end:
            end_time = datetime.strptime(end, "%H:%M").time()
            return now <= end_time

        return True

    def _match_arguments(self, pattern: dict, arguments: dict) -> bool:
        """Check if arguments match the pattern (supports regex on string values)."""
        for key, expected in pattern.items():
            if key not in arguments:
                return False
            actual = arguments[key]
            if isinstance(expected, str) and isinstance(actual, str):
                # Support regex patterns
                if not re.fullmatch(expected, actual):
                    return False
            elif isinstance(expected, dict):
                # Nested object matching
                if not isinstance(actual, dict):
                    return False
                if not self._match_arguments(expected, actual):
                    return False
            elif isinstance(expected, list):
                # Array matching - all patterns must match at least one element
                if not isinstance(actual, list):
                    return False
                for pattern_item in expected:
                    if not any(self._match_value(pattern_item, item) for item in actual):
                        return False
            else:
                # Exact match for other types
                if actual != expected:
                    return False
        return True

    def _match_value(self, pattern: Any, value: Any) -> bool:
        """Match a single value against a pattern."""
        if isinstance(pattern, str) and isinstance(value, str):
            return bool(re.fullmatch(pattern, value))
        elif isinstance(pattern, dict) and isinstance(value, dict):
            return self._match_arguments(pattern, value)
        else:
            return pattern == value


async def validate_arguments_against_schema(
    arguments: dict,
    schema: dict,
) -> tuple[bool, Optional[str]]:
    """Validate tool call arguments against the tool's JSON schema."""
    # Basic validation - in production, use jsonschema library
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for field in required:
        if field not in arguments:
            return False, f"Missing required field: {field}"

    # Check property types (basic)
    for key, value in arguments.items():
        if key in properties:
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            if expected_type and not _check_type(value, expected_type):
                return False, f"Field '{key}': expected type {expected_type}, got {type(value).__name__}"

    return True, None


def _check_type(value: Any, expected_type: str) -> bool:
    """Check if value matches expected JSON schema type."""
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    expected = type_map.get(expected_type)
    if expected is None:
        return True
    return isinstance(value, expected)
