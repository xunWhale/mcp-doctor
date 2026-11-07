"""Four ordered MCP checks with explicit skip semantics."""
from __future__ import annotations

import time
from typing import Any

from .model import Report, Stage
from .protocol import DiagnosticError, SUPPORTED_VERSIONS, inspect_tools, request, result_of
from .transport import Transport


class Runner:
    """Perform transport, initialize, ping, and tools/list checks in order."""

    def __init__(self, transport: Transport, kind: str, target: str, timeout: float = 5.0,
                 version: str = "2025-11-25") -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.transport = transport
        self.report = Report(kind, target)
        self.timeout = timeout
        self.version = version
        self.next_id = 1

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        ident = self.next_id
        self.next_id += 1
        response = self.transport.exchange(request(method, ident, params), self.timeout)
        return result_of(response, ident)

    def _stage(self, name: str, operation: Any) -> bool:
        start = time.monotonic()
        try:
            detail, evidence = operation()
            self.report.stages.append(Stage(name, "PASS", round((time.monotonic() - start) * 1000, 2), detail, evidence=evidence))
            return True
        except Exception as exc:
            # Keep machine output stable and avoid exposing traceback or environment secrets.
            advice = getattr(exc, "advice", "Inspect server logs and connection settings.")
            self.report.stages.append(Stage(name, "FAIL", round((time.monotonic() - start) * 1000, 2), str(exc), advice))
            return False

    def _skip_rest(self, names: list[str]) -> None:
        for name in names:
            self.report.stages.append(Stage(name, "SKIP", 0.0, "Skipped after prerequisite failure"))

    def _initialize(self) -> tuple[str, dict[str, Any]]:
        result = self._rpc("initialize", {
            "protocolVersion": self.version,
            "capabilities": {},
            "clientInfo": {"name": "mcp-doctor", "version": "0.1.0"},
        })
        if not isinstance(result, dict):
            raise DiagnosticError("initialize result must be an object", "Return initialize capabilities and protocolVersion.")
        version = result.get("protocolVersion")
        if not isinstance(version, str) or not version:
            raise DiagnosticError("Missing protocolVersion in initialize response", "Return the negotiated protocol version.")
        if version not in SUPPORTED_VERSIONS:
            raise DiagnosticError(f"Unsupported negotiated protocol version: {version}", "Choose a mutually supported MCP protocol version.")
        capabilities = result.get("capabilities")
        if not isinstance(capabilities, dict):
            raise DiagnosticError("Missing or invalid capabilities object", "Return capabilities as a JSON object.")
        self.report.protocol_version = version
        self.report.capabilities = capabilities
        self.transport.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return f"Initialized MCP {version}", {"protocol_version": version, "capabilities": capabilities}

    def _ping(self) -> tuple[str, dict[str, Any]]:
        result = self._rpc("ping")
        if not isinstance(result, dict):
            raise DiagnosticError("ping result must be an object", "Return an empty JSON object for ping.")
        return "Ping response received", {}

    def _tools(self) -> tuple[str, dict[str, Any]]:
        names: list[str] = []
        cursor: str | None = None
        seen: set[str] = set()
        for _ in range(100):
            params = {"cursor": cursor} if cursor else None
            result = self._rpc("tools/list", params)
            page = inspect_tools(result)
            for name in page:
                if name in names:
                    raise DiagnosticError(f"Duplicate tool name across pages: {name}", "Return unique names across pages.")
                names.append(name)
            next_cursor = result.get("nextCursor")
            if next_cursor is None:
                self.report.tools = names
                return f"Inspected {len(names)} tools", {"tool_count": len(names), "tool_names": names}
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen:
                raise DiagnosticError("Invalid or repeating tools/list cursor", "Return a unique nextCursor for each page.")
            seen.add(next_cursor)
            cursor = next_cursor
        raise DiagnosticError("Exceeded 100 tools/list pages", "Check pagination termination.")

    def run(self) -> Report:
        try:
            if not self._stage("transport", lambda: (self.transport.open() or "Connection established", {})):
                self._skip_rest(["handshake", "ping", "tools"])
            elif not self._stage("handshake", self._initialize):
                self._skip_rest(["ping", "tools"])
            else:
                self._stage("ping", self._ping)
                self._stage("tools", self._tools)
        finally:
            try:
                self.transport.close()
            except Exception:
                pass
        return self.report
