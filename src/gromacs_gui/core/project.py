from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gromacs_gui.core.step_state import STEP_ORDER, StepRecord, StepState
from gromacs_gui.project_io.filesystem import create_project_layout, step_dir
from gromacs_gui.project_io.project_file import ProjectManifest


class Project(QObject):
    """Orchestrates one simulation project: its folder layout, manifest, and
    per-step state. UI code should only talk to Project, never touch gmx or
    the filesystem directly.
    """

    state_changed = Signal()

    def __init__(self, root: Path, manifest: ProjectManifest) -> None:
        super().__init__()
        self.root = Path(root)
        self.manifest = manifest

    @classmethod
    def create(cls, root: Path) -> Project:
        root = Path(root)
        create_project_layout(root)
        project = cls(root, ProjectManifest.new())
        project.save()
        return project

    @classmethod
    def open(cls, root: Path) -> Project:
        root = Path(root)
        manifest = ProjectManifest.load(root)
        project = cls(root, manifest)
        project._reconcile_with_disk()
        return project

    def save(self) -> None:
        self.manifest.save(self.root)

    def step_dir(self, step_name: str) -> Path:
        return step_dir(self.root, step_name)

    def step_record(self, step_name: str) -> StepRecord:
        return self.manifest.steps[step_name]

    @staticmethod
    def compute_input_hash(*parts: bytes | str) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(part.encode() if isinstance(part, str) else part)
        return digest.hexdigest()

    def record_step_started(self, step_name: str, input_hash: str | None = None) -> None:
        record = self.step_record(step_name)
        record.state = StepState.RUNNING
        record.error_message = None
        if input_hash is not None:
            record.input_hash = input_hash
        self.save()
        self.state_changed.emit()

    def record_step_finished(self, step_name: str, output_files: list[str]) -> None:
        record = self.step_record(step_name)
        record.state = StepState.DONE
        record.output_files = list(output_files)
        record.error_message = None
        self._invalidate_downstream(step_name)
        self.save()
        self.state_changed.emit()

    def record_step_failed(self, step_name: str, error_message: str) -> None:
        record = self.step_record(step_name)
        record.state = StepState.FAILED
        record.error_message = error_message
        self.save()
        self.state_changed.emit()

    def _invalidate_downstream(self, step_name: str) -> None:
        index = STEP_ORDER.index(step_name)
        for downstream_name in STEP_ORDER[index + 1 :]:
            record = self.step_record(downstream_name)
            if record.state == StepState.DONE:
                record.state = StepState.STALE

    def _reconcile_with_disk(self) -> None:
        """Demote a step from DONE back to PENDING if its recorded output files
        are missing on disk (e.g. deleted/moved by hand outside the GUI), so the
        wizard doesn't claim a step is ready when it isn't.
        """
        changed = False
        for step_name in STEP_ORDER:
            record = self.step_record(step_name)
            if record.state != StepState.DONE:
                continue
            missing = [f for f in record.output_files if not (self.root / f).is_file()]
            if missing:
                record.state = StepState.PENDING
                record.output_files = []
                changed = True
        if changed:
            self.save()
