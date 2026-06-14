from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "crisismind" / "data" / "scenarios.json"


def load_dataset() -> dict[str, Any]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


class SimpleMCPServer:
    def __init__(self, server_name: str, tools: list[ToolDefinition]):
        self.server_name = server_name
        self.tools = {tool.name: tool for tool in tools}

    def serve_forever(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            response = self._handle_message(message)
            if response is not None:
                self._write_message(response)

    def _handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.server_name, "version": "0.1.0"},
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self.tools.values()
                    ]
                },
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool = self.tools.get(tool_name)
            if tool is None:
                return self._error(request_id, -32601, f"Unknown tool: {tool_name}")
            try:
                result = tool.handler(params.get("arguments", {}))
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result)}],
                        "structuredContent": result,
                        "isError": False,
                    },
                }
            except Exception as exc:
                return self._error(request_id, -32000, str(exc))

        if request_id is not None:
            return self._error(request_id, -32601, f"Unknown method: {method}")
        return None

    @staticmethod
    def _error(request_id: int | str | None, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def _read_message() -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = sys.stdin.buffer.readline()
            if line == b"":
                return None
            if line in {b"\r\n", b"\n"}:
                break
            decoded = line.decode("ascii").strip()
            if ":" in decoded:
                name, value = decoded.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise RuntimeError("Missing content-length header.")
        body = sys.stdin.buffer.read(content_length)
        if len(body) != content_length:
            raise RuntimeError("Incomplete MCP frame.")
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _write_message(message: dict[str, Any]) -> None:
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()
