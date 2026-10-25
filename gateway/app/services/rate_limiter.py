"""Rate limiting service using Redis."""
import time
from typing import Optional

import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()


class RateLimiter:
    """Redis-based rate limiter with sliding window."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._enabled = True

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
        except Exception:
            self._enabled = False
            self._redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _get_key(self, identifier: str, window: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"ratelimit:{identifier}:{window}"

    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, info_dict).
        """
        if not self._enabled or not self._redis:
            return True, {"allowed": True, "remaining": max_requests, "reset": 0}

        current_time = int(time.time())
        window_key = current_time // window_seconds
        key = self._get_key(identifier, str(window_key))

        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds * 2)
            results = await pipe.execute()

            current_count = results[0]
            remaining = max(0, max_requests - current_count)
            reset_time = (window_key + 1) * window_seconds

            allowed = current_count <= max_requests

            return allowed, {
                "allowed": allowed,
                "current": current_count,
                "remaining": remaining,
                "reset": reset_time,
                "limit": max_requests,
                "window": window_seconds,
            }
        except Exception:
            # Fail open on Redis errors
            return True, {"allowed": True, "remaining": max_requests, "reset": 0}

    async def get_current_usage(self, identifier: str, window_seconds: int) -> int:
        """Get current request count for identifier."""
        if not self._enabled or not self._redis:
            return 0

        current_time = int(time.time())
        window_key = current_time // window_seconds
        key = self._get_key(identifier, str(window_key))

        try:
            count = await self._redis.get(key)
            return int(count) if count else 0
        except Exception:
            return 0


class EgressController:
    """Controls egress requests to external URLs."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._enabled = True
        self._allowlist: list[str] = []

    async def initialize(self, allowlist: list[str]) -> None:
        """Initialize with egress allowlist."""
        self._allowlist = allowlist
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
        except Exception:
            self._enabled = False
            self._redis = None

    def is_allowed_url(self, url: str) -> bool:
        """Check if URL is in allowlist."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        for allowed in self._allowlist:
            allowed_parsed = urlparse(allowed)
            allowed_base = f"{allowed_parsed.scheme}://{allowed_parsed.netloc}"
            if base_url == allowed_base or base_url.startswith(allowed_base.rstrip("/") + "/"):
                return True
        return False

    async def check_egress_limit(
        self,
        identifier: str,
        url: str,
        max_requests: int = 10,
        window_seconds: int = 60,
        max_size_bytes: int = 10 * 1024 * 1024,  # 10 MB
    ) -> tuple[bool, dict]:
        """Check egress limits for a URL."""
        if not self.is_allowed_url(url):
            return False, {
                "allowed": False,
                "reason": "URL not in egress allowlist",
                "url": url,
            }

        if not self._enabled or not self._redis:
            return True, {"allowed": True, "remaining": max_requests}

        key = f"egress:{identifier}:{url}"
        current_time = int(time.time())
        window_key = current_time // window_seconds
        full_key = f"{key}:{window_key}"

        try:
            pipe = self._redis.pipeline()
            pipe.incr(full_key)
            pipe.expire(full_key, window_seconds * 2)
            results = await pipe.execute()

            current_count = results[0]
            remaining = max(0, max_requests - current_count)
            allowed = current_count <= max_requests

            return allowed, {
                "allowed": allowed,
                "current": current_count,
                "remaining": remaining,
                "limit": max_requests,
                "window": window_seconds,
            }
        except Exception:
            return True, {"allowed": True, "remaining": max_requests}

    async def check_response_size(self, size_bytes: int, max_size_bytes: int) -> tuple[bool, dict]:
        """Check if response size is within limits."""
        allowed = size_bytes <= max_size_bytes
        return allowed, {
            "allowed": allowed,
            "size_bytes": size_bytes,
            "max_size_bytes": max_size_bytes,
        }


class LoopDetector:
    """Detects runaway agent loops by tracking call patterns."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._enabled = True

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
        except Exception:
            self._enabled = False
            self._redis = None

    async def record_call(self, agent_id: str, tool_name: str) -> tuple[bool, dict]:
        """
        Record a tool call and check for loops.
        Returns (is_suspicious, details).
        """
        if not self._enabled or not self._redis:
            return False, {"suspicious": False}

        key = f"loop:{agent_id}"
        current_time = int(time.time())
        window_seconds = 60  # 1-minute window
        window_key = current_time // window_seconds

        try:
            # Use a sorted set to track calls with timestamps
            member = f"{tool_name}:{current_time}"
            await self._redis.zadd(key, {member: current_time})
            await self._redis.expire(key, window_seconds * 2)

            # Count calls in window
            count = await self._redis.zcount(key, current_time - window_seconds, current_time)

            # Count unique tools
            tools = await self._redis.zrange(key, 0, -1)
            unique_tools = set(t.split(":")[0] for t in tools)

            # Detect suspicious patterns
            suspicious = False
            reasons = []

            if count > 50:  # More than 50 calls per minute
                suspicious = True
                reasons.append(f"High call rate: {count}/min")

            if len(unique_tools) == 1 and count > 20:
                # Repeatedly calling the same tool
                suspicious = True
                reasons.append(f"Repeated same tool: {list(unique_tools)[0]}")

            # Check for alternating pattern (A->B->A->B)
            if len(tools) >= 4:
                recent_tools = [t.split(":")[0] for t in tools[-4:]]
                if recent_tools[0] == recent_tools[2] and recent_tools[1] == recent_tools[3]:
                    if recent_tools[0] != recent_tools[1]:
                        suspicious = True
                        reasons.append("Alternating tool pattern detected")

            return suspicious, {
                "suspicious": suspicious,
                "reasons": reasons,
                "call_count": count,
                "unique_tools": len(unique_tools),
                "window_seconds": window_seconds,
            }
        except Exception:
            return False, {"suspicious": False}


# Global instances
_rate_limiter: Optional[RateLimiter] = None
_egress_controller: Optional[EgressController] = None
_loop_detector: Optional[LoopDetector] = None


async def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        await _rate_limiter.initialize()
    return _rate_limiter


async def get_egress_controller() -> EgressController:
    """Get or create the global egress controller."""
    global _egress_controller
    if _egress_controller is None:
        _egress_controller = EgressController()
        await _egress_controller.initialize(settings.egress_allowlist_parsed)
    return _egress_controller


async def get_loop_detector() -> LoopDetector:
    """Get or create the global loop detector."""
    global _loop_detector
    if _loop_detector is None:
        _loop_detector = LoopDetector()
        await _loop_detector.initialize()
    return _loop_detector
