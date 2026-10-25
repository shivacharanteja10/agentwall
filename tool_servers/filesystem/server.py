"""Filesystem-like tool server for demo purposes."""
import json
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Filesystem Tool Server", version="1.0.0")

# Sandbox directory
SANDBOX_ROOT = Path("/tmp/agentwall_fs").resolve()
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)


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


def _safe_path(path: str) -> Path:
    """Resolve path within sandbox."""
    target = (SANDBOX_ROOT / path).resolve()
    if not str(target).startswith(str(SANDBOX_ROOT)):
        raise HTTPException(status_code=400, detail="Path traversal attempt")
    return target


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "filesystem"}


@app.post("/")
async def handle_rpc(request: JSONRPCRequest) -> JSONRPCResponse:
    request_id = request.id

    if request.method == "tools/list":
        tools = [
            {
                "name": "fs_read",
                "description": "Read a file from the sandbox filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to file"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "fs_write",
                "description": "Write a file to the sandbox filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to file"},
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "fs_list",
                "description": "List files in a directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative directory path", "default": "."},
                    },
                },
            },
            {
                "name": "fs_delete",
                "description": "Delete a file or directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to delete"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "fs_copy",
                "description": "Copy a file or directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string", "description": "Source path"},
                        "dst": {"type": "string", "description": "Destination path"},
                    },
                    "required": ["src", "dst"],
                },
            },
        ]
        return JSONRPCResponse(id=request_id, result={"tools": tools})

    elif request.method == "tools/call":
        params = request.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if name == "fs_read":
                path = _safe_path(arguments["path"])
                if not path.exists():
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "File not found"}], "isError": True},
                    )
                content = path.read_text(encoding="utf-8")
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": content}], "isError": False},
                )

            elif name == "fs_write":
                path = _safe_path(arguments["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(arguments["content"], encoding="utf-8")
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": f"Written to {arguments['path']}"}], "isError": False},
                )

            elif name == "fs_list":
                path = _safe_path(arguments.get("path", "."))
                if not path.exists():
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "Directory not found"}], "isError": True},
                    )
                items = []
                for item in path.iterdir():
                    items.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    })
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": json.dumps(items, indent=2)}], "isError": False},
                )

            elif name == "fs_delete":
                path = _safe_path(arguments["path"])
                if not path.exists():
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "Path not found"}], "isError": True},
                    )
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": f"Deleted {arguments['path']}"}], "isError": False},
                )

            elif name == "fs_copy":
                src = _safe_path(arguments["src"])
                dst = _safe_path(arguments["dst"])
                if not src.exists():
                    return JSONRPCResponse(
                        id=request_id,
                        result={"content": [{"type": "text", "text": "Source not found"}], "isError": True},
                    )
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                return JSONRPCResponse(
                    id=request_id,
                    result={"content": [{"type": "text", "text": f"Copied {arguments['src']} to {arguments['dst']}"}], "isError": False},
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
    uvicorn.run(app, host="0.0.0.0", port=8001)