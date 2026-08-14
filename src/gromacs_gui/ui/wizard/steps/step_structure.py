from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import (
    build_pdb2gmx_command,
    find_unsupported_heteroatoms,
    strip_crystal_waters,
)
from gromacs_gui.gmx.forcefields import gmxdata_top_dir, list_force_fields, list_water_models
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand


class StepStructureWidget(StepBase):
    step_name = "structure"

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self._input_path: Path | None = None
        self._input_label = QLabel("No file selected")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse_clicked)
        picker_row = QHBoxLayout()
        picker_row.addWidget(self._input_label, 1)
        picker_row.addWidget(browse_button)
        self.form_layout.addRow("Structure file (.pdb):", picker_row)

        self.force_field_combo = QComboBox()
        self.water_model_combo = QComboBox()
        self.form_layout.addRow("Force field:", self.force_field_combo)
        self.form_layout.addRow("Water model:", self.water_model_combo)

        self.strip_waters_checkbox = QCheckBox("Remove crystallographic water (HETATM HOH)")
        self.strip_waters_checkbox.setChecked(True)
        self.form_layout.addRow(self.strip_waters_checkbox)

        self._populate_force_fields()
        self.force_field_combo.currentIndexChanged.connect(self._populate_water_models)
        self._populate_water_models()

    def _populate_force_fields(self) -> None:
        top_dir = gmxdata_top_dir(self.gmx_env)
        if top_dir is None:
            return
        for ff in list_force_fields(top_dir):
            self.force_field_combo.addItem(f"{ff.name} — {ff.description}", userData=ff.name)

    def _populate_water_models(self) -> None:
        self.water_model_combo.clear()
        top_dir = gmxdata_top_dir(self.gmx_env)
        force_field = self.force_field_combo.currentData()
        if top_dir is None or not force_field:
            return
        for model in list_water_models(top_dir, force_field):
            label = f"{model.name} — {model.description}"
            self.water_model_combo.addItem(label, userData=model.name)

    def _on_browse_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a structure file", str(Path.home()), "Structure files (*.pdb *.gro)"
        )
        if not path:
            return
        self._input_path = Path(path)
        self._input_label.setText(self._input_path.name)

    def is_valid(self) -> bool:
        return (
            self._input_path is not None
            and self._input_path.is_file()
            and self.force_field_combo.currentData() is not None
            and self.water_model_combo.currentData() is not None
        )

    def build_commands(self) -> list[StepCommand]:
        assert self._input_path is not None
        structure_dir = self.project.step_dir(self.step_name)

        unsupported = find_unsupported_heteroatoms(self._input_path)
        if unsupported:
            QMessageBox.warning(
                self,
                "Unsupported heteroatoms",
                "This structure contains residues Phase 1 doesn't know how to "
                f"parameterize automatically: {', '.join(sorted(unsupported))}. "
                "pdb2gmx will likely fail on them; you may need to supply your own "
                "topology for these residues first.",
            )

        source_pdb = self._input_path
        if self.strip_waters_checkbox.isChecked():
            clean_pdb = structure_dir / "clean.pdb"
            strip_crystal_waters(source_pdb, clean_pdb)
            source_pdb = clean_pdb

        topology_dir = self.project.root / "topology"
        args = build_pdb2gmx_command(
            source_pdb,
            structure_dir / conventions.STRUCTURE_GRO,
            topology_dir / conventions.TOPOLOGY_TOP,
            topology_dir / conventions.POSRE_ITP,
            self.force_field_combo.currentData(),
            self.water_model_combo.currentData(),
        )
        return [StepCommand(args=args)]

    def output_files(self) -> list[str]:
        root = self.project.root
        structure_dir = self.project.step_dir(self.step_name)
        topology_dir = root / "topology"
        return [
            str((structure_dir / conventions.STRUCTURE_GRO).relative_to(root)),
            str((topology_dir / conventions.TOPOLOGY_TOP).relative_to(root)),
            str((topology_dir / conventions.POSRE_ITP).relative_to(root)),
        ]
