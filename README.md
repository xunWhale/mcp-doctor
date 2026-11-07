# mcp-doctor

Zero-runtime-dependency MCP diagnostics for Python 3.10+.

## Install

```bash
python -m pip install .
# or, without installing:
PYTHONPATH=src python -m mcp_doctor stdio 'python server.py'
```

## Usage

```bash
mcp-doctor stdio 'python server.py'
mcp-doctor stdio 'python server.py' --json --timeout 3
mcp-doctor sse 'http://127.0.0.1:8000/sse' --json
```

`stdio` launches a subprocess (do not run untrusted commands). `sse` uses **legacy HTTP+SSE** (`endpoint` event + POST), **not** Streamable HTTP. The CLI does not execute exposed tools. The checks are transport, initialize, ping, and tools/list. A failure in transport/handshake skips dependent stages; a failed ping still permits tools inspection. `tools/list` pagination is supported up to 100 pages. Tool schema validation is structural, not full JSON Schema meta-schema validation.

Exit status: 0 all stages PASS, 1 one or more FAIL/SKIP, 2 CLI argument error. `--json` prints one JSON object to stdout. Output can contain tool names and target commands; avoid publishing reports containing secrets.

## Development

```bash
python -m pip install -e '.[test]'
pytest -q
```

## Security and limitations

- No authentication options in v0.1; do not embed tokens in URLs or commands.
- Legacy SSE is same-origin only to reduce endpoint redirection risks. Only probe trusted hosts.
- Stdio stderr is discarded; consult server logs separately.
- SSE is a persistent HTTP stream; the stdlib socket timeout and reader thread do not guarantee clean cancellation of every blocked OS operation.
- This is a protocol diagnostic, not a sandbox or complete conformance certification.
