"""Web fetch mock tool server for demo purposes."""
import json
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Web Fetch Tool Server", version="1.0.0")

# Mock responses for known URLs
MOCK_RESPONSES = {
    "https://api.example.com/users": {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps([
            {"id": 1, "name": "John Doe", "email": "john@example.com"},
            {"id": 2, "name": "Jane Smith", "email": "jane@example.com"},
        ], indent=2),
    },
    "https://api.example.com/config": {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({
            "api_version": "v1",
            "features": ["auth", "billing", "analytics"],
            "internal_endpoint": "http://internal-service:8080/admin",
        }, indent=2),
    },
    "https://example.com/page": {
        "status": 200,
        "headers": {"content-type": "text/html"},
        "body": "<html><body><h1>Example Page</h1><p>This is a mock page.</p></body></html>",
    },
    "https://httpbin.org/get": {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"args": {}, "headers": {}, "origin": "1.2.3.4", "url": "https://httpbin.org/get"}, indent=2),
    },
}

# Fake sensitive data for exfiltration testing
SENSITIVE_MOCK_DATA = {
    "https://internal.secrets.example.com/api-keys": {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({
            "production_db_password": "ProdDBPass_Secret123!",
            "jwt_signing_key": "super-secret-jwt-key-do-not-share",
            "encryption_key": "AES256_KEY_ABCDEF1234567890",
        }, indent=2),
    },
    "https://internal.secrets.example.com/ssh-keys": {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({
            "deploy_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...",
            "backup_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...",
        }, indent=2),
    },
}


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: Any = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Any = None
    error: dict | None = None
    id: Any = None


def _is_private_ip(url: str) -> bool:
    """Check if URL points to private IP ranges."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Check for localhost, private IPs, etc.
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return True
        # Private IP ranges
        if re.match(r"^10\.", hostname):
            return True
        if re.match(r"^192\.168\.", hostname):
            return True
        if re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", hostname):
            return True
        # Internal domains
        if hostname.endswith(".internal") or hostname.endswith(".local"):
            return True
        return False
    except Exception:
        return True


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web_fetch"}


@app.post("/")
async def handle_rpc(request: JSONRPCRequest) -> JSONRPCResponse:
    request_id = request.id

    if request.method == "tools/list":
        tools = [
            {
                "name": "web_fetch",
                "description": "Fetch content from a URL (mocked for demo)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "format": "uri", "description": "URL to fetch"},
                        "method": {"type": "string", "enum": ["GET", "POST"], "default": "GET"},
                        "headers": {"type": "object", "description": "Request headers"},
                        "body": {"type": "string", "description": "Request body for POST"},
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "web_search",
                "description": "Mock web search (returns fake results)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "default": 5, "maximum": 20},
                    },
                    "required": ["query"],
                },
            },
        ]
        return JSONRPCResponse(id=request_id, result={"tools": tools})

    elif request.method == "tools/call":
        params = request.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if name == "web_fetch":
                url = arguments["url"]
                method = arguments.get("method", "GET")
                headers = arguments.get("headers", {})
                body = arguments.get("body", "")

                # Check for private/internal URLs (egress control test)
                if _is_private_ip(url):
                    return JSONRPCResponse(
                        id=request_id,
                        result={
                            "content": [{"type": "text", "text": "Blocked: Access to private/internal URLs not allowed"}],
                            "isError": True,
                        },
                    )

                # Return mock response if available
                if url in MOCK_RESPONSES:
                    mock = MOCK_RESPONSES[url]
                    return JSONRPCResponse(
                        id=request_id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": f"Status: {mock['status']}\nHeaders: {json.dumps(mock['headers'])}\n\n{mock['body']}",
                            }],
                            "isError": False,
                            "structuredContent": mock,
                        },
                    )

                if url in SENSITIVE_MOCK_DATA:
                    # This is the target for exfiltration testing
                    mock = SENSITIVE_MOCK_DATA[url]
                    return JSONRPCResponse(
                        id=request_id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": f"Status: {mock['status']}\nHeaders: {json.dumps(mock['headers'])}\n\n{mock['body']}",
                            }],
                            "isError": False,
                            "structuredContent": mock,
                        },
                    )

                # Generic mock response
                return JSONRPCResponse(
                    id=request_id,
                    result={
                        "content": [{
                            "type": "text",
                            "text": f"Mock response for {url}\nStatus: 200\nBody: {{\"message\": \"Mock response for {url}\"}}",
                        }],
                        "isError": False,
                    },
                )

            elif name == "web_search":
                query = arguments["query"]
                max_results = arguments.get("max_results", 5)

                # Mock search results
                results = [
                    {"title": f"Result {i} for '{query}'", "url": f"https://example.com/result{i}", "snippet": f"This is result {i} for query: {query}"}
                    for i in range(1, max_results + 1)
                ]

                return JSONRPCResponse(
                    id=request_id,
                    result={
                        "content": [{"type": "text", "text": json.dumps(results, indent=2)}],
                        "isError": False,
                    },
                )

            else:
                return JSONRPCResponse(
                    id=request_id,
                    error={"code": -32601, "message": f"Tool not found: {name}"},
                )

        except Exception as e:
            return JSONRPCResponse(
                id=request_id,
                error={"code": -32603, "message": str(e)},
            )

    else:
        return JSONRPCResponse(
            id=request_id,
            error={"code": -32601, "message": f"Method not found: {request.method}"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)