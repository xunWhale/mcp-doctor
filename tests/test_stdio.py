"""Real stdio pipes with a fake in-process Python MCP server; no external service."""
import json
import sys

import pytest

from mcp_doctor.protocol import DiagnosticError
from mcp_doctor.runner import Runner
from mcp_doctor.transport import StdioTransport


SERVER = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    method = msg["method"]
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}}
    elif method == "ping":
        result = {}
    else:
        result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n")
    sys.stdout.flush()
'''


def test_stdio_integration(tmp_path):
    server = tmp_path / "server.py"
    server.write_text(SERVER)
    transport = StdioTransport(f'"{sys.executable}" "{server}"')
    report = Runner(transport, "stdio", "test").run()
    assert report.ok
    assert report.tools == ["echo"]


def test_stdio_missing_executable():
    report = Runner(StdioTransport("definitely-not-an-executable-123456"), "stdio", "missing").run()
    assert report.stages[0].status == "FAIL"


def test_stdio_stdout_corruption(tmp_path):
    server = tmp_path / "broken.py"
    server.write_text('import sys\nprint("this is not JSON", flush=True)\nsys.stdin.readline()\n')
    report = Runner(StdioTransport(f'"{sys.executable}" "{server}"'), "stdio", "broken", timeout=1).run()
    assert report.stages[1].status == "FAIL"
    assert "Invalid JSON" in report.stages[1].detail


def test_stdio_timeout(tmp_path):
    server = tmp_path / "hanging.py"
    server.write_text('import time\ntime.sleep(10)\n')
    report = Runner(StdioTransport(f'"{sys.executable}" "{server}"'), "stdio", "hanging", timeout=0.1).run()
    assert report.stages[1].status == "FAIL"
    assert "timed out" in report.stages[1].detail
