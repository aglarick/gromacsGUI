from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STALE = "stale"


# Ordered Phase 1 pipeline; each step depends on every previous one being DONE.
# The index also drives the numbered folder layout (00_structure, 01_box, ...).
STEP_ORDER: tuple[str, ...] = (
    "structure",
    "box",
    "solvate",
    "ions",
    "em",
    "nvt",
    "npt",
    "production",
)


@dataclass
class StepRecord:
    name: str
    state: StepState = StepState.PENDING
    input_hash: str | None = None
    output_files: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "input_hash": self.input_hash,
            "output_files": list(self.output_files),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StepRecord:
        return cls(
            name=data["name"],
            state=StepState(data.get("state", StepState.PENDING.value)),
            input_hash=data.get("input_hash"),
            output_files=list(data.get("output_files", [])),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error_message=data.get("error_message"),
        )
