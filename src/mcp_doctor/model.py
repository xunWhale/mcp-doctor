"""Stable, JSON-serializable diagnostic results."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Stage:
    """One diagnostic stage, including actionable failure information."""

    name: str
    status: str
    duration_ms: float
    detail: str
    advice: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    """Aggregate report suitable for a CI machine-readable contract."""

    transport: str
    target: str
    stages: list[Stage] = field(default_factory=list)
    protocol_version: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.stages) and all(s.status == "PASS" for s in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}
