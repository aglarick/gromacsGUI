from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gromacs_gui.core.step_state import STEP_ORDER, StepRecord
from gromacs_gui.project_io.filesystem import manifest_path

SCHEMA_VERSION = 1


@dataclass
class ProjectManifest:
    schema_version: int = SCHEMA_VERSION
    gmx_version: str | None = None
    force_field: str | None = None
    water_model: str | None = None
    steps: dict[str, StepRecord] = field(default_factory=dict)

    @classmethod
    def new(cls) -> ProjectManifest:
        return cls(steps={name: StepRecord(name=name) for name in STEP_ORDER})

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "gmx_version": self.gmx_version,
            "force_field": self.force_field,
            "water_model": self.water_model,
            "steps": [self.steps[name].to_dict() for name in STEP_ORDER if name in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectManifest:
        steps = {record["name"]: StepRecord.from_dict(record) for record in data.get("steps", [])}
        for name in STEP_ORDER:
            steps.setdefault(name, StepRecord(name=name))
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            gmx_version=data.get("gmx_version"),
            force_field=data.get("force_field"),
            water_model=data.get("water_model"),
            steps=steps,
        )

    def save(self, project_root: Path) -> None:
        manifest_path(project_root).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, project_root: Path) -> ProjectManifest:
        data = json.loads(manifest_path(project_root).read_text())
        return cls.from_dict(data)
