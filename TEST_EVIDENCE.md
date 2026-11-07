# mcp-doctor Verification Evidence

## Unit Tests (34 / 34 passed)
```console
$ pytest tests/ -v
/home/fish/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:300: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-9.2.0, pluggy-1.7.0 -- /home/fish/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/fish/projects/mcp-doctor
configfile: pyproject.toml
plugins: asyncio-1.4.1.post1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 34 items

tests/test_cli.py::test_json_output PASSED                               [  2%]
tests/test_cli.py::test_text_output PASSED                               [  5%]
tests/test_protocol.py::test_request PASSED                              [  8%]
tests/test_protocol.py::test_invalid_response[None] PASSED               [ 11%]
tests/test_protocol.py::test_invalid_response[response1] PASSED          [ 14%]
tests/test_protocol.py::test_invalid_response[response2] PASSED          [ 17%]
tests/test_protocol.py::test_invalid_response[response3] PASSED          [ 20%]
tests/test_protocol.py::test_invalid_response[response4] PASSED          [ 23%]
tests/test_protocol.py::test_invalid_response[response5] PASSED          [ 26%]
tests/test_protocol.py::test_result PASSED                               [ 29%]
tests/test_protocol.py::test_tools_valid PASSED                          [ 32%]
tests/test_protocol.py::test_tools_invalid[None] PASSED                  [ 35%]
tests/test_protocol.py::test_tools_invalid[tools1] PASSED                [ 38%]
tests/test_protocol.py::test_tools_invalid[tools2] PASSED                [ 41%]
tests/test_protocol.py::test_tools_invalid[tools3] PASSED                [ 44%]
tests/test_protocol.py::test_tools_invalid[tools4] PASSED                [ 47%]
tests/test_protocol.py::test_tools_invalid[tools5] PASSED                [ 50%]
tests/test_protocol.py::test_tools_invalid[tools6] PASSED                [ 52%]
tests/test_runner.py::test_success_four_stages PASSED                    [ 55%]
tests/test_runner.py::test_stage_failures[transport-expected0] PASSED    [ 58%]
tests/test_runner.py::test_stage_failures[initialize-expected1] PASSED   [ 61%]
tests/test_runner.py::test_stage_failures[ping-expected2] PASSED         [ 64%]
tests/test_runner.py::test_stage_failures[tools/list-expected3] PASSED   [ 67%]
tests/test_runner.py::test_unsupported_protocol PASSED                   [ 70%]
tests/test_runner.py::test_invalid_capabilities PASSED                   [ 73%]
tests/test_runner.py::test_duplicate_tools PASSED                        [ 76%]
tests/test_runner.py::test_timeout_validation PASSED                     [ 79%]
tests/test_runner.py::test_pagination PASSED                             [ 82%]
tests/test_sse.py::test_legacy_sse_end_to_end PASSED                     [ 85%]
tests/test_sse.py::test_sse_bad_url PASSED                               [ 88%]
tests/test_stdio.py::test_stdio_integration PASSED                       [ 91%]
tests/test_stdio.py::test_stdio_missing_executable PASSED                [ 94%]
tests/test_stdio.py::test_stdio_stdout_corruption PASSED                 [ 97%]
tests/test_stdio.py::test_stdio_timeout PASSED                           [100%]

============================== 34 passed in 2.66s ==============================
```

## Real-world End-to-End Stdio Diagnostic
Tested against real MCP server `gif2grid-mcp`:
```console
$ mcp-doctor stdio "/home/fish/projects/gif2grid-mcp/.venv/bin/python -m gif2grid_mcp.server"
MCP DOCTOR | stdio | /home/fish/projects/gif2grid-mcp/.venv/bin/python -m gif2grid_mcp.server
[PASS] transport       0.35 ms | Connection established
[PASS] handshake     287.97 ms | Initialized MCP 2025-11-25
[PASS] ping            0.81 ms | Ping response received
[PASS] tools           0.79 ms | Inspected 1 tools
Result: PASS
```

## Machine-Readable JSON Mode
```console
$ mcp-doctor stdio "/home/fish/projects/gif2grid-mcp/.venv/bin/python -m gif2grid_mcp.server" --json
{"capabilities": {"prompts": {"listChanged": false}, "resources": {"listChanged": false, "subscribe": false}, "tools": {"listChanged": false}}, "ok": true, "protocol_version": "2025-11-25", "stages": [{"advice": "", "detail": "Connection established", "duration_ms": 0.37, "evidence": {}, "name": "transport", "status": "PASS"}, {"advice": "", "detail": "Initialized MCP 2025-11-25", "duration_ms": 289.16, "evidence": {"capabilities": {"prompts": {"listChanged": false}, "resources": {"listChanged": false, "subscribe": false}, "tools": {"listChanged": false}}, "protocol_version": "2025-11-25"}, "name": "handshake", "status": "PASS"}, {"advice": "", "detail": "Ping response received", "duration_ms": 0.72, "evidence": {}, "name": "ping", "status": "PASS"}, {"advice": "", "detail": "Inspected 1 tools", "duration_ms": 0.82, "evidence": {"tool_count": 1, "tool_names": ["gif_to_grid"]}, "name": "tools", "status": "PASS"}], "target": "/home/fish/projects/gif2grid-mcp/.venv/bin/python -m gif2grid_mcp.server", "tools": ["gif_to_grid"], "transport": "stdio"}
```
