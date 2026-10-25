"""Client for communicating with upstream tool servers."""
import json
from typing import Optional

import httpx
from app.core.config import get_settings
from app.schemas import (
    JSONRPCRequest,
    JSONRPCResponse,
    ToolCallResult,
    ToolDefinition,
)
from pydantic import BaseModel

settings = get_settings()


class UpstreamServerConfig(BaseModel):
    """Configuration for an upstream tool server."""
    name: str
    base_url: str
    timeout: float = 30.0


class UpstreamClient:
    """Client for making JSON-RPC calls to upstream tool servers."""

    def __init__(self, config: UpstreamServerConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "UpstreamClient":
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout),
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(self, method: str, params: Optional[dict] = None) -> JSONRPCResponse:
        """Make a JSON-RPC request to the upstream server."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        request = JSONRPCRequest(method=method, params=params or {}, id=1)

        try:
            response = await self._client.post(
                "/",
                json=request.model_dump(exclude_none=True),
            )
            response.raise_for_status()
            data = response.json()
            return JSONRPCResponse(**data)
        except httpx.HTTPStatusError as e:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=1,
                error={
                    "code": -32603,
                    "message": f"Upstream server error: {e.response.status_code}",
                    "data": e.response.text[:500],
                },
            )
        except httpx.RequestError as e:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=1,
                error={
                    "code": -32603,
                    "message": f"Upstream connection error: {str(e)}",
                },
            )
        except json.JSONDecodeError as e:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=1,
                error={
                    "code": -32700,
                    "message": f"Parse error: {str(e)}",
                },
            )

    async def list_tools(self) -> list[ToolDefinition]:
        """Get list of available tools from upstream server."""
        response = await self._request("tools/list")
        if response.error:
            raise Exception(f"Failed to list tools: {response.error['message']}")

        result = response.result or {}
        tools_data = result.get("tools", [])
        return [ToolDefinition(**tool) for tool in tools_data]

    async def call_tool(self, name: str, arguments: dict) -> ToolCallResult:
        """Call a tool on the upstream server."""
        response = await self._request("tools/call", {"name": name, "arguments": arguments})

        if response.error:
            return ToolCallResult(
                content=[{"type": "text", "text": f"Error: {response.error['message']}"}],
                isError=True,
            )

        result = response.result or {}
        return ToolCallResult(
            content=result.get("content", []),
            isError=result.get("isError", False),
            structuredContent=result.get("structuredContent"),
        )

    async def health_check(self) -> bool:
        """Check if upstream server is healthy."""
        try:
            if not self._client:
                return False
            response = await self._client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False


class UpstreamManager:
    """Manages connections to multiple upstream tool servers."""

    def __init__(self):
        self._clients: dict[str, UpstreamClient] = {}
        self._configs: dict[str, UpstreamServerConfig] = {}
        self._tool_to_server: dict[str, str] = {}

    def register_server(self, config: UpstreamServerConfig) -> None:
        """Register an upstream tool server."""
        self._configs[config.name] = config

    async def initialize(self) -> None:
        """Initialize all clients and discover tools."""
        for name, config in self._configs.items():
            async with UpstreamClient(config) as client:
                try:
                    tools = await client.list_tools()
                    for tool in tools:
                        self._tool_to_server[tool.name] = name
                except Exception:
                    pass  # Server might not be ready yet

    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the server name that provides a given tool."""
        return self._tool_to_server.get(tool_name)

    async def call_tool(self, tool_name: str, arguments: dict) -> ToolCallResult:
        """Call a tool on the appropriate upstream server."""
        server_name = self.get_server_for_tool(tool_name)
        if not server_name:
            return ToolCallResult(
                content=[{"type": "text", "text": f"Tool not found: {tool_name}"}],
                isError=True,
            )

        config = self._configs[server_name]
        async with UpstreamClient(config) as client:
            return await client.call_tool(tool_name, arguments)

    async def list_all_tools(self) -> list[ToolDefinition]:
        """List all tools from all registered servers."""
        all_tools = []
        for name, config in self._configs.items():
            async with UpstreamClient(config) as client:
                try:
                    tools = await client.list_tools()
                    all_tools.extend(tools)
                except Exception:
                    pass
        return all_tools

    def get_registered_servers(self) -> list[str]:
        """Get list of registered server names."""
        return list(self._configs.keys())


# Global upstream manager
_upstream_manager: Optional[UpstreamManager] = None


def get_upstream_manager() -> UpstreamManager:
    """Get or create the global upstream manager."""
    global _upstream_manager
    if _upstream_manager is None:
        _upstream_manager = UpstreamManager()
        # Register default servers from config
        _upstream_manager.register_server(UpstreamServerConfig(
            name="filesystem",
            base_url=settings.filesystem_server_url,
        ))
        _upstream_manager.register_server(UpstreamServerConfig(
            name="database",
            base_url=settings.database_server_url,
        ))
        _upstream_manager.register_server(UpstreamServerConfig(
            name="web_fetch",
            base_url=settings.web_fetch_server_url,
        ))
    return _upstream_manager
