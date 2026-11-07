"""Loopback-only fake legacy SSE server: no external MCP installation."""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp_doctor.runner import Runner
from mcp_doctor.transport import SSETransport


def test_legacy_sse_end_to_end():
    events = queue.Queue()
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b"event: endpoint\ndata: /messages\n\n")
            self.wfile.flush()
            ready.set()
            while True:
                try:
                    msg = events.get(timeout=3)
                except queue.Empty:
                    break
                try:
                    self.wfile.write(b"event: message\ndata: " + json.dumps(msg).encode() + b"\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
            self.close_connection = True

        def do_POST(self):
            size = int(self.headers["Content-Length"])
            msg = json.loads(self.rfile.read(size))
            if "id" in msg:
                if msg["method"] == "initialize":
                    result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}}
                elif msg["method"] == "ping":
                    result = {}
                else:
                    result = {"tools": [{"name": "x", "inputSchema": {"type": "object"}}]}
                events.put({"jsonrpc": "2.0", "id": msg["id"], "result": result})
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/sse"
        report = Runner(SSETransport(url, timeout=2), "sse", url, timeout=2).run()
        assert report.ok, report.to_dict()
        assert report.tools == ["x"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_sse_bad_url():
    report = Runner(SSETransport("file:///etc/passwd"), "sse", "invalid").run()
    assert [s.status for s in report.stages] == ["FAIL", "SKIP", "SKIP", "SKIP"]
