from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLineEdit, QWidget

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.solvate import DEFAULT_SOLVENT_BOX, build_solvate_command
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand


class StepSolvateWidget(StepBase):
    step_name = "solvate"

    DESCRIPTION = "Llena la caja con moléculas de solvente (agua u otro) alrededor de tu molécula."

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        # A categorized solvent library with pre-equilibrated boxes is a planned
        # future milestone (see project notes); for now this accepts any box gmx
        # can resolve, defaulting to the built-in water box.
        self.solvent_box_edit = QLineEdit(DEFAULT_SOLVENT_BOX)
        self.form_layout.addRow("Solvent box (-cs):", self.solvent_box_edit)

    def _input_gro(self) -> Path:
        return self.project.step_dir("box") / conventions.BOX_GRO

    def _topology_top(self) -> Path:
        return self.project.root / "topology" / conventions.TOPOLOGY_TOP

    def is_valid(self) -> bool:
        return self._input_gro().is_file() and bool(self.solvent_box_edit.text().strip())

    def build_commands(self) -> list[StepCommand]:
        output_gro = self.project.step_dir(self.step_name) / conventions.SOLVATE_GRO
        args = build_solvate_command(
            self._input_gro(),
            self._topology_top(),
            output_gro,
            solvent_box=self.solvent_box_edit.text().strip(),
        )
        return [StepCommand(args=args)]

    def output_files(self) -> list[str]:
        output_gro = self.project.step_dir(self.step_name) / conventions.SOLVATE_GRO
        return [str(output_gro.relative_to(self.project.root))]
