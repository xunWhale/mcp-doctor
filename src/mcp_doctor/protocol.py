"""Minimal JSON-RPC 2.0 and MCP protocol validation helpers."""
from __future__ import annotations

from typing import Any

# These are client preferences, not a promise that every server supports them.
SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


class DiagnosticError(Exception):
    """A diagnostic failure with a suggested repair."""

    def __init__(self, message: str, advice: str = "") -> None:
        super().__init__(message)
        self.advice = advice


def request(method: str, request_id: int, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construct a JSON-RPC request; notifications use a separate function."""
    data: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        data["params"] = params
    return data


def result_of(message: Any, request_id: int) -> Any:
    """Reject invalid or remote-error JSON-RPC replies."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        raise DiagnosticError("Response is not a JSON-RPC 2.0 object", "Check stdout/HTTP response framing.")
    if message.get("id") != request_id or isinstance(message.get("id"), bool):
        raise DiagnosticError("Response ID does not match request", "Inspect concurrent request routing.")
    if "error" in message:
        raise DiagnosticError(f"Remote JSON-RPC error: {message['error']}", "Inspect server logs and method support.")
    if "result" not in message:
        raise DiagnosticError("JSON-RPC response has no result", "Return a JSON-RPC result or error object.")
    return message["result"]


def inspect_tools(result: Any) -> list[str]:
    """Validate tools/list structure and basic JSON Schema object shape.

    This is deliberately NOT a full JSON Schema meta-schema validator.
    """
    if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
        raise DiagnosticError("tools/list result must contain a tools array", "Return {'tools': [...]}.")
    names: list[str] = []
    for index, tool in enumerate(result["tools"]):
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
            raise DiagnosticError(f"Tool #{index} has no non-empty name", "Declare a unique string tool name.")
        name = tool["name"]
        if name in names:
            raise DiagnosticError(f"Duplicate tool name: {name}", "Give every exposed tool a unique name.")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise DiagnosticError(f"Tool {name}: inputSchema must be an object schema", "Set inputSchema to {'type': 'object', 'properties': {...}}.")
        if "properties" in schema and not isinstance(schema["properties"], dict):
            raise DiagnosticError(f"Tool {name}: properties must be an object", "Use a JSON object for properties.")
        if "required" in schema and (not isinstance(schema["required"], list) or
            any(not isinstance(v, str) for v in schema["required"])):
            raise DiagnosticError(f"Tool {name}: required must be an array of strings", "Fix inputSchema.required.")
        names.append(name)
    return names
