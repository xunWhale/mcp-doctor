"""Stdio and legacy HTTP+SSE MCP transports using only the standard library.

SSE mode means the legacy GET event stream with an `endpoint` event and POST
message endpoint, not the newer Streamable HTTP transport.
"""
from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from .protocol import DiagnosticError

MAX_LINE = 2 * 1024 * 1024


class Transport(Protocol):
    def open(self) -> None: ...
    def exchange(self, message: dict[str, Any], timeout: float) -> dict[str, Any]: ...
    def notify(self, message: dict[str, Any]) -> None: ...
    def close(self) -> None: ...


class StdioTransport:
    """Launch an MCP server and exchange newline-delimited JSON-RPC messages.

    A daemon reader thread prevents a blocking readline from defeating timeouts.
    stdout must contain protocol messages only; diagnostics belong on stderr.
    """

    def __init__(self, command: str) -> None:
        self.command = command
        self.process: subprocess.Popen[bytes] | None = None
        self.inbox: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self.pending: dict[Any, dict[str, Any]] = {}

    def open(self) -> None:
        try:
            argv = shlex.split(self.command, posix=os.name != "nt")
            if not argv:
                raise DiagnosticError("Empty command", "Provide an executable command.")
            self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0)
        except (OSError, ValueError) as exc:
            raise DiagnosticError(f"Cannot launch command: {exc}", "Verify executable, PATH, arguments and permissions.") from exc
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            for raw in self.process.stdout:
                if len(raw) > MAX_LINE:
                    raise DiagnosticError("Oversized stdio message", "Reduce server response size.")
                try:
                    item = json.loads(raw)
                except (ValueError, UnicodeError) as exc:
                    raise DiagnosticError(f"Invalid JSON on stdout: {exc}", "Send logs to stderr, not stdout.") from exc
                if isinstance(item, dict):
                    self.inbox.put(item)
            self.inbox.put(DiagnosticError("Server stdout closed", "Check server crash logs and process lifecycle."))
        except Exception as exc:
            self.inbox.put(exc)

    def notify(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None or self.process.poll() is not None:
            raise DiagnosticError("Server process is not running", "Check the server startup command.")
        try:
            self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except OSError as exc:
            raise DiagnosticError(f"Cannot write to server stdin: {exc}", "Check server lifecycle.") from exc

    def exchange(self, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        self.notify(message)
        ident = message["id"]
        deadline = time.monotonic() + timeout
        if ident in self.pending:
            return self.pending.pop(ident)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DiagnosticError(f"Request {message['method']} timed out", "Inspect server blocking calls and timeout configuration.")
            try:
                item = self.inbox.get(timeout=remaining)
            except queue.Empty as exc:
                raise DiagnosticError(f"Request {message['method']} timed out", "Inspect server blocking calls and timeout configuration.") from exc
            if isinstance(item, Exception):
                raise DiagnosticError(str(item), getattr(item, "advice", "Inspect server logs.")) from item
            if "id" not in item:  # Ignore server notifications, including progress.
                continue
            if item["id"] == ident:
                return item
            self.pending[item["id"]] = item

    def close(self) -> None:
        if self.process is not None:
            if self.process.stdin:
                self.process.stdin.close()
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
            if self.process.stdout:
                self.process.stdout.close()


class SSETransport:
    """Legacy MCP SSE transport (GET stream + endpoint event + POST messages).

    For security, the endpoint must have the same scheme and host as the SSE URL.
    """

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout
        self.endpoint: str | None = None
        self.stream: Any = None
        self.inbox: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self.pending: dict[Any, dict[str, Any]] = {}
        self._ready = threading.Event()
        self._failure: Exception | None = None

    def open(self) -> None:
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise DiagnosticError("SSE URL must be http(s)", "Provide a valid legacy SSE endpoint URL.")
        try:
            req = urllib.request.Request(self.url, headers={"Accept": "text/event-stream"})
            self.stream = urllib.request.urlopen(req, timeout=self.timeout)
            if "text/event-stream" not in self.stream.headers.get("Content-Type", ""):
                raise DiagnosticError("Server did not return text/event-stream", "Use the legacy SSE endpoint, not Streamable HTTP.")
        except (OSError, urllib.error.URLError) as exc:
            raise DiagnosticError(f"Cannot open SSE stream: {exc}", "Check URL, TLS, port and server availability.") from exc
        threading.Thread(target=self._reader, daemon=True).start()
        if not self._ready.wait(self.timeout):
            self.close()
            raise DiagnosticError("SSE endpoint event timed out", "Ensure the server sends an endpoint event promptly.")
        if self._failure:
            raise DiagnosticError(str(self._failure), "Check SSE endpoint event and server logs.")

    def _reader(self) -> None:
        event = "message"
        data: list[str] = []
        try:
            while True:
                raw = self.stream.readline(MAX_LINE + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE:
                    raise DiagnosticError("Oversized SSE line")
                line = raw.decode("utf-8").rstrip("\r\n")
                if line == "":
                    if data:
                        self._dispatch(event, "\n".join(data))
                    event, data = "message", []
                elif line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].lstrip(" "))
            raise DiagnosticError("SSE stream closed", "Check server disconnects and proxy buffering.")
        except Exception as exc:
            if not self._ready.is_set():
                self._failure = exc
                self._ready.set()
            self.inbox.put(exc)

    def _dispatch(self, event: str, payload: str) -> None:
        if event == "endpoint":
            endpoint = urllib.parse.urljoin(self.url, payload)
            original, target = urllib.parse.urlsplit(self.url), urllib.parse.urlsplit(endpoint)
            if (original.scheme, original.netloc) != (target.scheme, target.netloc):
                self._failure = DiagnosticError("Cross-origin SSE POST endpoint rejected")
            else:
                self.endpoint = endpoint
            self._ready.set()
        elif event == "message":
            try:
                item = json.loads(payload)
                if isinstance(item, dict):
                    self.inbox.put(item)
            except ValueError as exc:
                self.inbox.put(DiagnosticError(f"Invalid SSE JSON: {exc}"))

    def notify(self, message: dict[str, Any]) -> None:
        if not self.endpoint:
            raise DiagnosticError("No SSE POST endpoint discovered")
        data = json.dumps(message).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status not in (200, 202, 204):
                    raise DiagnosticError(f"Unexpected POST status: {response.status}")
        except (OSError, urllib.error.URLError) as exc:
            raise DiagnosticError(f"SSE POST failed: {exc}", "Check POST endpoint and proxy rules.") from exc

    def exchange(self, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        self.notify(message)
        ident = message["id"]
        deadline = time.monotonic() + timeout
        if ident in self.pending:
            return self.pending.pop(ident)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DiagnosticError(f"Request {message['method']} timed out", "Check SSE event delivery and proxy buffering.")
            try:
                item = self.inbox.get(timeout=remaining)
            except queue.Empty as exc:
                raise DiagnosticError(f"Request {message['method']} timed out", "Check SSE event delivery and proxy buffering.") from exc
            if isinstance(item, Exception):
                raise DiagnosticError(str(item), getattr(item, "advice", "Check SSE stream.")) from item
            if "id" not in item:
                continue
            if item["id"] == ident:
                return item
            self.pending[item["id"]] = item

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
