import pytest

from mcp_doctor.protocol import DiagnosticError
from mcp_doctor.runner import Runner


class FakeTransport:
    def __init__(self, fail=None, tools=None, version="2025-11-25", capabilities=None):
        self.fail = fail
        self.tools = tools if tools is not None else [{"name": "echo", "inputSchema": {"type": "object"}}]
        self.version = version
        self.capabilities = {"tools": {}} if capabilities is None else capabilities
        self.sent = []
        self.closed = False

    def open(self):
        if self.fail == "transport":
            raise DiagnosticError("port refused", "Start the server")

    def notify(self, message):
        self.sent.append(message)

    def exchange(self, message, timeout):
        self.sent.append(message)
        method = message["method"]
        if self.fail == method:
            raise DiagnosticError("simulated failure", "Repair simulated fault")
        if method == "initialize":
            result = {"protocolVersion": self.version, "capabilities": self.capabilities}
        elif method == "ping":
            result = {}
        else:
            result = {"tools": self.tools}
        return {"jsonrpc": "2.0", "id": message["id"], "result": result}

    def close(self):
        self.closed = True


def test_success_four_stages():
    fake = FakeTransport()
    report = Runner(fake, "stdio", "fake").run()
    assert report.ok
    assert [s.status for s in report.stages] == ["PASS"] * 4
    assert report.tools == ["echo"]
    assert report.protocol_version == "2025-11-25"
    assert fake.closed
    assert any(x.get("method") == "notifications/initialized" for x in fake.sent)
    assert all(s.duration_ms >= 0 for s in report.stages)


@pytest.mark.parametrize("fault,expected", [
    ("transport", ["FAIL", "SKIP", "SKIP", "SKIP"]),
    ("initialize", ["PASS", "FAIL", "SKIP", "SKIP"]),
    ("ping", ["PASS", "PASS", "FAIL", "PASS"]),
    ("tools/list", ["PASS", "PASS", "PASS", "FAIL"]),
])
def test_stage_failures(fault, expected):
    fake = FakeTransport(fail=fault)
    report = Runner(fake, "stdio", "fake").run()
    assert [s.status for s in report.stages] == expected
    assert not report.ok
    assert fake.closed
    assert "advice" in report.to_dict()["stages"][0]


def test_unsupported_protocol():
    report = Runner(FakeTransport(version="1900-01-01"), "stdio", "fake").run()
    assert report.stages[1].status == "FAIL"


def test_invalid_capabilities():
    report = Runner(FakeTransport(capabilities=[]), "stdio", "fake").run()
    assert report.stages[1].status == "FAIL"


def test_duplicate_tools():
    tool = {"name": "x", "inputSchema": {"type": "object"}}
    report = Runner(FakeTransport(tools=[tool, tool]), "stdio", "fake").run()
    assert report.stages[3].status == "FAIL"


def test_timeout_validation():
    with pytest.raises(ValueError):
        Runner(FakeTransport(), "stdio", "fake", timeout=0)


class PaginatedTransport(FakeTransport):
    def exchange(self, message, timeout):
        if message["method"] != "tools/list":
            return super().exchange(message, timeout)
        cursor = (message.get("params") or {}).get("cursor")
        result = ({"tools": [{"name": "a", "inputSchema": {"type": "object"}}], "nextCursor": "p2"}
                  if cursor is None else {"tools": [{"name": "b", "inputSchema": {"type": "object"}}]})
        return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def test_pagination():
    report = Runner(PaginatedTransport(), "stdio", "fake").run()
    assert report.ok and report.tools == ["a", "b"]
