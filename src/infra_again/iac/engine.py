"""IaC engine abstraction for INFRA-AGAIN."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class IaCStage(str, Enum):
    """Sub-stages within IaC execution."""
    NOT_STARTED = "NOT_STARTED"
    IAC_RENDERED = "IAC_RENDERED"
    IAC_INITIALIZED = "IAC_INITIALIZED"
    IAC_VALIDATED = "IAC_VALIDATED"
    IAC_PLANNED = "IAC_PLANNED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    IAC_APPLYING = "IAC_APPLYING"
    IAC_APPLIED = "IAC_APPLIED"


class IaCEngine(ABC):
    """Abstract IaC execution engine."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        ...

    @abstractmethod
    async def probe(self) -> str | None:
        """Return version string or None if not installed."""
        ...

    @abstractmethod
    async def fmt(self, working_dir: Path) -> IaCResult:
        """Format and check configuration."""
        ...

    @abstractmethod
    async def init(self, working_dir: Path) -> IaCResult:
        """Initialize provider plugins."""
        ...

    @abstractmethod
    async def validate(self, working_dir: Path) -> IaCResult:
        """Validate configuration syntax."""
        ...

    @abstractmethod
    async def plan(self, working_dir: Path, plan_path: Path) -> IaCResult:
        """Generate and save execution plan."""
        ...

    @abstractmethod
    async def apply(self, working_dir: Path, plan_path: Path) -> IaCResult:
        """Apply a saved plan."""
        ...

    @abstractmethod
    async def output(self, working_dir: Path) -> dict[str, Any]:
        """Get outputs as dict."""
        ...

    @abstractmethod
    async def show(self, plan_path: Path) -> dict[str, Any]:
        """Show plan in machine-readable format."""
        ...

    @abstractmethod
    def state_reference(self, working_dir: Path) -> str:
        """Return the path to the IaC state file."""
        ...

    @abstractmethod
    async def destroy(self, working_dir: Path) -> IaCResult:
        """Destroy resources (GATED by policy upstream)."""
        ...


@dataclass
class IaCResult:
    """Result of an IaC engine operation."""
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class PlanInfo:
    """Extracted plan metadata."""
    resource_changes: list[dict[str, Any]] = field(default_factory=list)
    create_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    plan_checksum: str = ""
    raw_plan_json: dict[str, Any] | None = None
