from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QLineEdit, QSpinBox, QWidget

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.genion import build_genion_command, genion_stdin
from gromacs_gui.gmx.commands.grompp import build_grompp_command
from gromacs_gui.mdp.defaults import default_mdp_path
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand


class StepIonsWidget(StepBase):
    step_name = "ions"

    DESCRIPTION = (
        "Replaces some solvent molecules with ions, to neutralize the "
        "system's overall electric charge."
    )

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self.positive_ion_edit = QLineEdit("NA")
        self.negative_ion_edit = QLineEdit("CL")
        self.neutral_checkbox = QCheckBox("Neutralize system charge")
        self.neutral_checkbox.setChecked(True)
        self.maxwarn_spin = QSpinBox()
        self.maxwarn_spin.setRange(0, 20)
        self.maxwarn_spin.setValue(1)

        self.form_layout.addRow("Positive ion:", self.positive_ion_edit)
        self.form_layout.addRow("Negative ion:", self.negative_ion_edit)
        self.form_layout.addRow(self.neutral_checkbox)
        self.form_layout.addRow("grompp -maxwarn:", self.maxwarn_spin)

    def _input_gro(self) -> Path:
        return self.project.step_dir("solvate") / conventions.SOLVATE_GRO

    def _topology_top(self) -> Path:
        return self.project.root / "topology" / conventions.TOPOLOGY_TOP

    def is_valid(self) -> bool:
        return self._input_gro().is_file()

    def build_commands(self) -> list[StepCommand]:
        step_dir = self.project.step_dir(self.step_name)
        ions_tpr = step_dir / conventions.IONS_TPR
        ionized_gro = step_dir / conventions.IONS_GRO
        topology_top = self._topology_top()

        grompp_args = build_grompp_command(
            default_mdp_path("ions"),
            self._input_gro(),
            topology_top,
            ions_tpr,
            maxwarn=self.maxwarn_spin.value(),
        )
        genion_args = build_genion_command(
            ions_tpr,
            topology_top,
            ionized_gro,
            positive_ion=self.positive_ion_edit.text().strip() or "NA",
            negative_ion=self.negative_ion_edit.text().strip() or "CL",
            neutral=self.neutral_checkbox.isChecked(),
        )
        return [
            StepCommand(args=grompp_args),
            StepCommand(args=genion_args, stdin=genion_stdin()),
        ]

    def output_files(self) -> list[str]:
        ionized_gro = self.project.step_dir(self.step_name) / conventions.IONS_GRO
        return [str(ionized_gro.relative_to(self.project.root))]
