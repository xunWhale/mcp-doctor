"""Dependency-free command-line interface and CI output contract."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .protocol import SUPPORTED_VERSIONS
from .runner import Runner
from .transport import SSETransport, StdioTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-doctor", description="Diagnose MCP stdio and legacy SSE servers")
    sub = parser.add_subparsers(dest="transport", required=True)
    for name in ("stdio", "sse"):
        p = sub.add_parser(name, help="stdio server command" if name == "stdio" else "legacy SSE URL")
        p.add_argument("target", help="Quoted executable command" if name == "stdio" else "SSE GET URL")
        p.add_argument("--json", action="store_true", help="Emit JSON only")
        p.add_argument("--timeout", type=float, default=5.0, help="Timeout per request in seconds")
        p.add_argument("--version", choices=SUPPORTED_VERSIONS, default=SUPPORTED_VERSIONS[0])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        build_parser().error("--timeout must be greater than zero")
    transport = StdioTransport(args.target) if args.transport == "stdio" else SSETransport(args.target, args.timeout)
    report = Runner(transport, args.transport, args.target, args.timeout, args.version).run()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(f"MCP DOCTOR | {report.transport} | {report.target}")
        for stage in report.stages:
            print(f"[{stage.status:4}] {stage.name:10} {stage.duration_ms:9.2f} ms | {stage.detail}")
            if stage.advice:
                print(f"       Fix: {stage.advice}")
        print(f"Result: {'PASS' if report.ok else 'FAIL'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
