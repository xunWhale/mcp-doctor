import pytest

from mcp_doctor.protocol import DiagnosticError, inspect_tools, request, result_of


def test_request():
    assert request("ping", 1) == {"jsonrpc": "2.0", "id": 1, "method": "ping"}


@pytest.mark.parametrize("response", [None, [], {}, {"jsonrpc": "1.0", "id": 1, "result": {}},
                                       {"jsonrpc": "2.0", "id": 2, "result": {}},
                                       {"jsonrpc": "2.0", "id": 1, "error": {"code": -1}}])
def test_invalid_response(response):
    with pytest.raises(DiagnosticError):
        result_of(response, 1)


def test_result():
    assert result_of({"jsonrpc": "2.0", "id": 3, "result": {}}, 3) == {}


def test_tools_valid():
    assert inspect_tools({"tools": [{"name": "read", "inputSchema": {"type": "object", "properties": {}, "required": []}}]}) == ["read"]


@pytest.mark.parametrize("tools", [None, {}, [{"name": "x"}],
                                    [{"name": "x", "inputSchema": {"type": "string"}}],
                                    [{"name": "x", "inputSchema": {"type": "object", "properties": []}}],
                                    [{"name": "x", "inputSchema": {"type": "object", "required": [1]}}],
                                    [{"name": "x", "inputSchema": {"type": "object"}},
                                     {"name": "x", "inputSchema": {"type": "object"}}]])
def test_tools_invalid(tools):
    with pytest.raises(DiagnosticError):
        inspect_tools({"tools": tools})
