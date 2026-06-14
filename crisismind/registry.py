from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .models import AnalysisRequest, IntegrationStatus


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DEFAULT_MCP_CONFIG = PACKAGE_DIR / "data" / "mcp_servers.json"


class RegistryProtocol(Protocol):
    mode: str

    def weather_snapshot(self, request: AnalysisRequest) -> dict[str, Any]: ...
    def map_context(self) -> dict[str, Any]: ...
    def shelters(self) -> list[dict[str, Any]]: ...
    def critical_sites(self) -> dict[str, list[dict[str, Any]]]: ...
    def contacts(self) -> dict[str, str]: ...
    def resources(self) -> dict[str, int]: ...
    def checklist(self) -> list[str]: ...
    def tools_used(self) -> list[str]: ...
    def data_sources_used(self) -> list[str]: ...
    def integration_status(self) -> list[IntegrationStatus]: ...


class RegistryBase:
    mode = "local"

    def __init__(self) -> None:
        self._tool_log: list[str] = []
        self._tool_seen: set[str] = set()

    def _record_tool(self, tool_name: str) -> None:
        if tool_name not in self._tool_seen:
            self._tool_seen.add(tool_name)
            self._tool_log.append(tool_name)

    def tools_used(self) -> list[str]:
        return list(self._tool_log)


class LocalDatasetRegistry(RegistryBase):
    """In-process fallback registry used when MCP is disabled or unavailable."""

    mode = "local"

    def __init__(self, dataset: dict[str, Any]):
        super().__init__()
        self.dataset = dataset

    def weather_snapshot(self, request: AnalysisRequest) -> dict[str, Any]:
        self._record_tool("local.weather.snapshot")
        return {
            "rainfall_mm": request.rainfall_mm,
            "wind_kph": request.wind_kph,
            "temperature_c": request.temperature_c,
            "river_level": request.river_level,
            "aqi": request.air_quality_index,
        }

    def map_context(self) -> dict[str, Any]:
        self._record_tool("local.maps.context")
        return {
            "regions": self.dataset["regions"],
            "roads": self.dataset["roads"],
        }

    def shelters(self) -> list[dict[str, Any]]:
        self._record_tool("local.maps.shelters")
        return self.dataset["safe_zones"]

    def critical_sites(self) -> dict[str, list[dict[str, Any]]]:
        self._record_tool("local.maps.critical_sites")
        return {
            "hospitals": self.dataset["hospitals"],
            "schools": self.dataset["schools"],
        }

    def contacts(self) -> dict[str, str]:
        self._record_tool("local.command.contacts")
        return self.dataset["emergency_contacts"]

    def resources(self) -> dict[str, int]:
        self._record_tool("local.command.resources")
        return self.dataset["resources"]

    def checklist(self) -> list[str]:
        self._record_tool("local.command.checklist")
        return self.dataset["supply_checklist"]

    def data_sources_used(self) -> list[str]:
        return [
            "Local weather adapter",
            "Local maps adapter",
            "Local command data adapter",
        ]

    def integration_status(self) -> list[IntegrationStatus]:
        return [
            IntegrationStatus(
                server_name="Local Dataset Adapters",
                transport="in-process",
                connected=True,
                tools=[
                    "local.weather.snapshot",
                    "local.maps.context",
                    "local.maps.shelters",
                    "local.maps.critical_sites",
                    "local.command.contacts",
                    "local.command.resources",
                    "local.command.checklist",
                ],
                detail="Using in-process fallback adapters only.",
            )
        ]


@dataclass(frozen=True)
class MCPServerSpec:
    key: str
    label: str
    transport: str
    command: list[str]
    cwd: str | None = None


@dataclass
class MCPServerState:
    spec: MCPServerSpec
    connected: bool = False
    tools: list[str] = field(default_factory=list)
    detail: str = "Not initialized."


class MCPProtocolError(RuntimeError):
    pass


class MCPStdioClient:
    def __init__(self, spec: MCPServerSpec):
        self.spec = spec
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.RLock()
        self._next_id = 0

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._ensure_started_locked()
            result = self._request_locked("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            raise MCPProtocolError(f"{self.spec.label} returned an error for {name}.")
        structured = result.get("structuredContent")
        if structured is not None:
            return structured
        content = result.get("content", [])
        text_parts = [item["text"] for item in content if item.get("type") == "text" and "text" in item]
        if len(text_parts) == 1:
            try:
                return json.loads(text_parts[0])
            except json.JSONDecodeError:
                return {"text": text_parts[0]}
        return {"content": content}

    def list_tools(self) -> list[str]:
        with self._lock:
            self._ensure_started_locked()
            result = self._request_locked("tools/list", {})
        tools = result.get("tools", [])
        return [tool["name"] for tool in tools if "name" in tool]

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _ensure_started_locked(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        self._close_locked()
        try:
            self._process = subprocess.Popen(
                self.spec.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=self.spec.cwd or str(PROJECT_ROOT),
            )
            self._next_id = 0
            self._request_locked(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "Disaster Detection AI", "version": "0.2.0"},
                },
            )
            self._notify_locked("notifications/initialized", {})
        except Exception:
            self._close_locked()
            raise

    def _request_locked(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        process = self._require_process_locked()
        self._next_id += 1
        request_id = self._next_id
        self._write_message_locked(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        while True:
            message = self._read_message_locked()
            if "id" in message and message["id"] == request_id:
                if "error" in message:
                    error = message["error"]
                    raise MCPProtocolError(f"{method} failed: {error.get('message', 'Unknown error')}")
                return message.get("result", {})
            if "method" in message:
                continue
            if process.poll() is not None:
                raise MCPProtocolError(f"{self.spec.label} exited unexpectedly.")

    def _notify_locked(self, method: str, params: dict[str, Any]) -> None:
        self._write_message_locked({"jsonrpc": "2.0", "method": method, "params": params})

    def _write_message_locked(self, message: dict[str, Any]) -> None:
        process = self._require_process_locked()
        assert process.stdin is not None
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        process.stdin.write(header)
        process.stdin.write(body)
        process.stdin.flush()

    def _read_message_locked(self) -> dict[str, Any]:
        process = self._require_process_locked()
        assert process.stdout is not None
        headers: dict[str, str] = {}
        while True:
            line = process.stdout.readline()
            if line == b"":
                raise MCPProtocolError(f"{self.spec.label} closed the stdio stream.")
            if line in {b"\r\n", b"\n"}:
                break
            decoded = line.decode("ascii").strip()
            if ":" in decoded:
                name, value = decoded.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise MCPProtocolError(f"{self.spec.label} sent an invalid MCP frame.")
        body = process.stdout.read(content_length)
        if len(body) != content_length:
            raise MCPProtocolError(f"{self.spec.label} sent an incomplete MCP frame.")
        return json.loads(body.decode("utf-8"))

    def _require_process_locked(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise MCPProtocolError(f"{self.spec.label} is not running.")
        return self._process

    def _close_locked(self) -> None:
        if self._process is None:
            return
        process = self._process
        self._process = None
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
        except Exception:
            if process.poll() is None:
                process.kill()


class MCPBackedRegistry(RegistryBase):
    mode = "mcp"

    def __init__(self, dataset: dict[str, Any], specs: list[MCPServerSpec]):
        super().__init__()
        self._fallback = LocalDatasetRegistry(dataset)
        self._clients = {spec.key: MCPStdioClient(spec) for spec in specs}
        self._states = {spec.key: MCPServerState(spec=spec) for spec in specs}
        atexit.register(self.close)

    def close(self) -> None:
        for client in self._clients.values():
            client.close()

    def weather_snapshot(self, request: AnalysisRequest) -> dict[str, Any]:
        return self._call_or_fallback(
            server_key="weather",
            tool_name="weather.snapshot",
            arguments={"request": request.model_dump(mode="json")},
            fallback=lambda: self._fallback.weather_snapshot(request),
        )

    def map_context(self) -> dict[str, Any]:
        return self._call_or_fallback(
            server_key="maps",
            tool_name="maps.context",
            arguments={},
            fallback=self._fallback.map_context,
        )

    def shelters(self) -> list[dict[str, Any]]:
        result = self._call_or_fallback(
            server_key="maps",
            tool_name="maps.shelters",
            arguments={},
            fallback=self._fallback.shelters,
        )
        return list(result)

    def critical_sites(self) -> dict[str, list[dict[str, Any]]]:
        return self._call_or_fallback(
            server_key="maps",
            tool_name="maps.critical_sites",
            arguments={},
            fallback=self._fallback.critical_sites,
        )

    def contacts(self) -> dict[str, str]:
        return self._call_or_fallback(
            server_key="command",
            tool_name="command.contacts",
            arguments={},
            fallback=self._fallback.contacts,
        )

    def resources(self) -> dict[str, int]:
        return self._call_or_fallback(
            server_key="command",
            tool_name="command.resources",
            arguments={},
            fallback=self._fallback.resources,
        )

    def checklist(self) -> list[str]:
        result = self._call_or_fallback(
            server_key="command",
            tool_name="command.checklist",
            arguments={},
            fallback=self._fallback.checklist,
        )
        return list(result)

    def data_sources_used(self) -> list[str]:
        sources: list[str] = []
        for status in self.integration_status():
            suffix = "connected" if status.connected else "fallback to local dataset"
            sources.append(f"{status.server_name} ({suffix})")
        return sources

    def integration_status(self) -> list[IntegrationStatus]:
        statuses: list[IntegrationStatus] = []
        for server_key, state in self._states.items():
            self._refresh_status(server_key)
            statuses.append(
                IntegrationStatus(
                    server_name=state.spec.label,
                    transport=state.spec.transport,
                    connected=state.connected,
                    tools=state.tools,
                    detail=state.detail,
                )
            )
        return statuses

    def _call_or_fallback(
        self,
        server_key: str,
        tool_name: str,
        arguments: dict[str, Any],
        fallback: Callable[[], Any],
    ) -> Any:
        client = self._clients.get(server_key)
        state = self._states[server_key]
        if client is None:
            state.connected = False
            state.detail = "Server mapping is missing; using local dataset fallback."
            return fallback()
        try:
            result = client.call_tool(tool_name, arguments)
            self._record_tool(tool_name)
            self._refresh_status(server_key, warm=False)
            state.connected = True
            state.detail = f"Connected via stdio to {state.spec.label}."
            return result
        except Exception as exc:
            state.connected = False
            state.detail = f"{exc} Using local dataset fallback."
            self._record_tool(f"fallback.{tool_name}")
            return fallback()

    def _refresh_status(self, server_key: str, warm: bool = True) -> None:
        client = self._clients[server_key]
        state = self._states[server_key]
        if not warm and state.tools:
            return
        try:
            state.tools = client.list_tools()
            state.connected = True
            state.detail = f"Connected via stdio to {state.spec.label}."
        except Exception as exc:
            state.connected = False
            state.detail = f"{exc} Using local dataset fallback."


def build_registry(dataset: dict[str, Any], prefer_mcp: bool = True) -> RegistryProtocol:
    if not prefer_mcp or _is_truthy(os.getenv("CRISISMIND_DISABLE_MCP")):
        return LocalDatasetRegistry(dataset)
    specs = load_mcp_server_specs()
    if not specs:
        return LocalDatasetRegistry(dataset)
    return MCPBackedRegistry(dataset, specs)


def load_mcp_server_specs(config_path: str | Path | None = None) -> list[MCPServerSpec]:
    path = Path(os.getenv("CRISISMIND_MCP_CONFIG") or config_path or DEFAULT_MCP_CONFIG)
    raw = json.loads(path.read_text(encoding="utf-8"))
    servers = raw.get("servers", {})
    specs: list[MCPServerSpec] = []
    variables = {
        "python": sys.executable,
        "project_root": str(PROJECT_ROOT),
        "package_dir": str(PACKAGE_DIR),
    }
    for key, value in servers.items():
        command = [_expand_template(part, variables) for part in value["command"]]
        cwd = _expand_template(value["cwd"], variables) if value.get("cwd") else None
        specs.append(
            MCPServerSpec(
                key=key,
                label=value["label"],
                transport=value.get("transport", "stdio"),
                command=command,
                cwd=cwd,
            )
        )
    return specs


def _expand_template(value: str, variables: dict[str, str]) -> str:
    return value.format(**variables)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
