"""
Filesystem MCP Server

Provides file read, write, list, search, and metadata operations
via the Model Context Protocol (JSON-RPC over stdio).

Usage:
    python -m app.mcp_providers.filesystem.server --allowed-dir /path/to/allowed
"""

import argparse
import json
import os
import sys
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.mcp_providers.filesystem.permissions import (
    FilesystemPermissionEnforcer,
    PathPermissionError,
)

SERVER_INFO = {
    "name": "friday-filesystem",
    "version": "1.0.0",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates parent directories if needed)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the directory"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_info",
        "description": "Get metadata about a file or directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern within a directory tree",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', '**/*.md')"},
                "root": {"type": "string", "description": "Root directory to search from"},
            },
            "required": ["pattern", "root"],
        },
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file or empty directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to delete"},
            },
            "required": ["path"],
        },
    },
]


class FilesystemMCPServer:
    def __init__(self, allowed_directory: str) -> None:
        self._enforcer = FilesystemPermissionEnforcer(
            allowed_directories=[allowed_directory]
        )

    def handle_initialize(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        return {
            "protocolVersion": "0.1.0",
            "capabilities": {"tools": {}},
            "serverInfo": dict(SERVER_INFO),
        }

    def handle_list_tools(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        return {"tools": TOOLS}

    def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments", {})
        handler = getattr(self, f"tool_{name}", None)
        if handler is None:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }
        try:
            result = handler(args)
            return {"content": [{"type": "text", "text": result}]}
        except PathPermissionError as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }
        except FileNotFoundError as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }
        except IsADirectoryError as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }
        except PermissionError as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }

    def tool_read_file(self, args: Dict[str, Any]) -> str:
        path = self._enforcer.resolve(args["path"])
        return path.read_text(encoding="utf-8")

    def tool_write_file(self, args: Dict[str, Any]) -> str:
        path = self._enforcer.resolve(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"Written {len(args['content'])} bytes to {path}"

    def tool_list_directory(self, args: Dict[str, Any]) -> str:
        path = self._enforcer.resolve(args["path"])
        if not path.is_dir():
            return json.dumps({"error": f"Not a directory: {path}"})
        entries = []
        for child in sorted(path.iterdir()):
            try:
                stat = child.stat()
                entries.append({
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except OSError:
                continue
        return json.dumps(entries, indent=2)

    def tool_file_info(self, args: Dict[str, Any]) -> str:
        path = self._enforcer.resolve(args["path"])
        stat = path.stat()
        info = {
            "name": path.name,
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "permissions": oct(stat.st_mode & 0o777),
        }
        return json.dumps(info, indent=2)

    def tool_search_files(self, args: Dict[str, Any]) -> str:
        root = self._enforcer.resolve(args["root"])
        pattern = args["pattern"]
        matches = []
        for p in root.rglob("*"):
            try:
                if p.is_file() and fnmatch.fnmatch(p.name, pattern):
                    matches.append(str(p.relative_to(root)))
            except OSError:
                continue
        return json.dumps(matches, indent=2)

    def tool_delete_file(self, args: Dict[str, Any]) -> str:
        path = self._enforcer.resolve(args["path"])
        if path.is_file():
            path.unlink()
            return f"Deleted file: {path}"
        elif path.is_dir():
            try:
                path.rmdir()
                return f"Deleted empty directory: {path}"
            except OSError:
                raise IsADirectoryError(f"Directory not empty: {path}")
        raise FileNotFoundError(f"Not found: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Filesystem MCP Server")
    parser.add_argument(
        "--allowed-dir",
        required=True,
        action="append",
        dest="allowed_dirs",
        help="Allowed directory (may be specified multiple times)",
    )
    args = parser.parse_args()
    allowed = args.allowed_dirs or ["/tmp"]

    server = FilesystemMCPServer(allowed_directory=allowed[0])

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params")

        handlers = {
            "initialize": server.handle_initialize,
            "ping": lambda p: {},
            "tools/list": server.handle_list_tools,
            "tools/call": server.handle_call_tool,
        }

        handler = handlers.get(method)
        if handler is None:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        else:
            try:
                payload = handler(params)
                response = {"jsonrpc": "2.0", "id": req_id, "result": payload}
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)},
                }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
