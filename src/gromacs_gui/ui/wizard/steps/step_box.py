from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QWidget

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.editconf import build_editconf_command
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand

_BOX_TYPES = ["cubic", "dodecahedron", "octahedron", "triclinic"]


class StepBoxWidget(StepBase):
    step_name = "box"

    DESCRIPTION = (
        "Defines the simulation box around your molecule: its shape, and "
        "how far the atoms should stay from the edge (so the molecule "
        "doesn't interact with itself across the periodic boundary "
        "conditions)."
    )

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self.box_type_combo = QComboBox()
        self.box_type_combo.addItems(_BOX_TYPES)
        self.form_layout.addRow("Box shape:", self.box_type_combo)

        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.1, 5.0)
        self.distance_spin.setSingleStep(0.1)
        self.distance_spin.setValue(1.0)
        self.distance_spin.setSuffix(" nm")
        self.form_layout.addRow("Distance to edge:", self.distance_spin)

        self.center_checkbox = QCheckBox("Center molecule in box")
        self.center_checkbox.setChecked(True)
        self.form_layout.addRow(self.center_checkbox)

    def _input_gro(self) -> Path:
        return self.project.step_dir("structure") / conventions.STRUCTURE_GRO

    def is_valid(self) -> bool:
        return self._input_gro().is_file()

    def build_commands(self) -> list[StepCommand]:
        output_gro = self.project.step_dir(self.step_name) / conventions.BOX_GRO
        args = build_editconf_command(
            self._input_gro(),
            output_gro,
            box_type=self.box_type_combo.currentText(),
            distance_nm=self.distance_spin.value(),
            center=self.center_checkbox.isChecked(),
        )
        return [StepCommand(args=args)]

    def output_files(self) -> list[str]:
        output_gro = self.project.step_dir(self.step_name) / conventions.BOX_GRO
        return [str(output_gro.relative_to(self.project.root))]
