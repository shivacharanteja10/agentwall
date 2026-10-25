"""Database-like tool server with seeded fake data for demo purposes."""
import json
import random
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Database Tool Server", version="1.0.0")

# Seed fake data
USERS = [
    {"id": 1, "username": "alice", "email": "alice@example.com", "role": "admin", "created_at": "2024-01-15T10:00:00Z"},
    {"id": 2, "username": "bob", "email": "bob@example.com", "role": "user", "created_at": "2024-02-20T14:30:00Z"},
    {"id": 3, "username": "charlie", "email": "charlie@example.com", "role": "user", "created_at": "2024-03-10T09:15:00Z"},
    {"id": 4, "username": "diana", "email": "diana@example.com", "role": "operator", "created_at": "2024-04-05T16:45:00Z"},
    {"id": 5, "username": "eve", "email": "eve@example.com", "role": "viewer", "created_at": "2024-05-12T11:20:00Z"},
]

PRODUCTS = [
    {"id": 1, "name": "Widget A", "price": 29.99, "stock": 100, "category": "widgets"},
    {"id": 2, "name": "Widget B", "price": 49.99, "stock": 50, "category": "widgets"},
    {"id": 3, "name": "Gadget X", "price": 99.99, "stock": 25, "category": "gadgets"},
    {"id": 4, "name": "Gadget Y", "price": 149.99, "stock": 10, "category": "gadgets"},
    {"id": 5, "name": "Tool Z", "price": 19.99, "stock": 200, "category": "tools"},
]

ORDERS = [
    {"id": 1, "user_id": 1, "product_id": 1, "quantity": 2, "total": 59.98, "status": "completed", "created_at": "2024-06-01T10:00:00Z"},
    {"id": 2, "user_id": 2, "product_id": 3, "quantity": 1, "total": 99.99, "status": "completed", "created_at": "2024-06-02T14:30:00Z"},
    {"id": 3, "user_id": 3, "product_id": 2, "quantity": 3, "total": 149.97, "status": "pending", "created_at": "2024-06-03T09:15:00Z"},
    {"id": 4, "user_id": 1, "product_id": 5, "quantity": 5, "total": 99.95, "status": "shipped", "created_at": "2024-06-04T16:45:00Z"},
    {"id": 5, "user_id": 4, "product_id": 4, "quantity": 1, "total": 149.99, "status": "completed", "created_at": "2024-06-05T11:20:00Z"},
]

# Fake credentials for red team testing (clearly fake prefixes to avoid secret scanning)
FAKE_CREDENTIALS = {
    "api_keys": {
        "stripe": "sk_fake_abcdefghijklmnopqrstuvwxyz123456",
        "aws": "AKIAIOSFODNN7EXAMPLE",
        "github": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    },
    "database_passwords": {
        "primary": "SuperSecretDBPass123!",
        "replica": "AnotherSecretPass456@",
    },
    "internal_tokens": {
        "service_mesh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.token",
        "ci_cd": "ci_token_abcdef1234567890",
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


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "database"}


@app.post("/")
async def handle_rpc(request: JSONRPCRequest) -> JSONRPCResponse:
    request_id = request.id

    if request.method == "tools/list":
        tools = [
            {
                "name": "db_query",
                "description": "Execute a read-only SQL-like query on seeded data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "enum": ["users", "products", "orders"], "description": "Table to query"},
                        "filter": {"type": "object", "description": "Filter conditions (key-value pairs)"},
                        "limit": {"type": "integer", "default": 10, "maximum": 100},
                    },
                    "required": ["table"],
                },
            },
            {
                "name": "db_get_user",
                "description": "Get user by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "User ID"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "db_get_product",
                "description": "Get product by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                    },
                    "required": ["product_id"],
                },
            },
            {
                "name": "db_get_orders",
                "description": "Get orders for a user",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "User ID"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "db_internal_credentials",
                "description": "INTERNAL: Get system credentials (RESTRICTED)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "system": {"type": "string", "description": "System name"},
                    },
                    "required": ["system"],
                },
            },
        ]
        return JSONRPCResponse(id=request_id, result={"tools": tools})

    elif request.method == "tools/call":
        params = request.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if name == "db_query":
                table = arguments["table"]
                filter_cond = arguments.get("filter", {})
                limit = arguments.get("limit", 10)

                data = {"users": USERS, "products": PRODUCTS, "orders": ORDERS}.get(table, [])

                # Apply filters
                filtered = []
                for row in data:
                    match = True
                    for key, value in filter_cond.items():
                        if row.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered.append(row)

                return JSONRPCResponse(
                    id=request_id,
                    result={
                        "content": [{"type": "text", "text": json.dumps(filtered[:limit], indent=2)}],
                        "isError": False,
                    },
                )

            elif name == "db_get_user":
                user_id = arguments["user_id"]
                user = next((u for u in USERS if u["id"] == user_id), None)
                if not user:
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "User not found"}], "isError": True},
                    )
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": json.dumps(user, indent=2)}], "isError": False},
                )

            elif name == "db_get_product":
                product_id = arguments["product_id"]
                product = next((p for p in PRODUCTS if p["id"] == product_id), None)
                if not product:
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "Product not found"}], "isError": True},
                    )
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": json.dumps(product, indent=2)}], "isError": False},
                )

            elif name == "db_get_orders":
                user_id = arguments["user_id"]
                user_orders = [o for o in ORDERS if o["user_id"] == user_id]
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": json.dumps(user_orders, indent=2)}], "isError": False},
                )

            elif name == "db_internal_credentials":
                # This is the target for red team testing - should be blocked by policy
                system = arguments["system"]
                creds = FAKE_CREDENTIALS.get(system, {})
                return JSONRPCResponse(
                    id=request_id,
                    result={
                        "content": [{"type": "text", "text": json.dumps(creds, indent=2)}],
                        "isError": False,
                        "structuredContent": creds,
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
    uvicorn.run(app, host="0.0.0.0", port=8002)