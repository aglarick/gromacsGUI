from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import (
    build_pdb2gmx_command,
    list_heteroatom_residues,
    remove_residues,
)
from gromacs_gui.gmx.forcefields import gmxdata_top_dir, list_force_fields, list_water_models
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand

_CLEANUP_HELP_TEXT = (
    "HETATM son átomos que no forman parte de la cadena principal de la "
    "proteína (agua, iones u otras moléculas presentes en los datos "
    "cristalográficos). Se seleccionan por defecto todos los residuos HETATM "
    "para eliminarlos — desmarca los que quieras conservar."
)


class StepStructureWidget(StepBase):
    step_name = "structure"

    DESCRIPTION = (
        "Prepara la molécula que vas a simular: a partir de un archivo de "
        "coordenadas, obtienes un .gro y una topología (los parámetros de "
        "campo de fuerza) listos para el resto del flujo. Si ya tienes ambos "
        "—por ejemplo, de ATB o LigParGen— puedes saltarte la generación e "
        "indicar directamente dónde están tus archivos."
    )

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self._input_path: Path | None = None
        self._own_coords_path: Path | None = None
        self._own_topology_path: Path | None = None
        self._residue_checkboxes: dict[str, QCheckBox] = {}

        self._build_mode_selector()
        self._build_generate_section()
        self._build_bring_own_section()

        self._populate_force_fields()
        self.force_field_combo.currentIndexChanged.connect(self._populate_water_models)
        self._populate_water_models()

        self._generate_radio.toggled.connect(self._update_mode_visibility)
        self._update_mode_visibility()

    # --- construction ---
    def _build_mode_selector(self) -> None:
        self._generate_radio = QRadioButton(
            "Generar topología con pdb2gmx (tengo solo coordenadas o datos "
            "cristalográficos, sin campo de fuerza asignado)"
        )
        self._bring_own_radio = QRadioButton(
            "Ya tengo estructura y topología (de ATB, LigParGen, u otra fuente)"
        )
        self._generate_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self._generate_radio)
        mode_group.addButton(self._bring_own_radio)

        mode_box = QWidget(self)
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(QLabel("¿Qué tienes?"))
        mode_layout.addWidget(self._generate_radio)
        mode_layout.addWidget(self._bring_own_radio)
        self.form_layout.addRow(mode_box)

    def _build_generate_section(self) -> None:
        self._generate_container = QWidget(self)
        generate_form = self._new_subform(self._generate_container)

        self._input_label = QLabel("No file selected")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse_structure_clicked)
        picker_row = QHBoxLayout()
        picker_row.addWidget(self._input_label, 1)
        picker_row.addWidget(browse_button)
        generate_form.addRow("Structure file (.pdb or .gro):", picker_row)

        self._cleanup_group = QGroupBox("Limpiar estructura")
        cleanup_layout = QVBoxLayout(self._cleanup_group)
        help_label = QLabel(_CLEANUP_HELP_TEXT)
        help_label.setWordWrap(True)
        cleanup_layout.addWidget(help_label)
        self._residue_list_layout = QVBoxLayout()
        cleanup_layout.addLayout(self._residue_list_layout)
        self._cleanup_group.setVisible(False)
        generate_form.addRow(self._cleanup_group)

        self.force_field_combo = QComboBox()
        self.water_model_combo = QComboBox()
        generate_form.addRow("Force field:", self.force_field_combo)
        generate_form.addRow("Water model:", self.water_model_combo)

        self.form_layout.addRow(self._generate_container)

    def _build_bring_own_section(self) -> None:
        self._bring_own_container = QWidget(self)
        bring_own_form = self._new_subform(self._bring_own_container)

        self._own_coords_label = QLabel("No file selected")
        own_coords_button = QPushButton("Browse…")
        own_coords_button.clicked.connect(self._on_browse_own_coords_clicked)
        own_coords_row = QHBoxLayout()
        own_coords_row.addWidget(self._own_coords_label, 1)
        own_coords_row.addWidget(own_coords_button)
        bring_own_form.addRow("Coordinate file (.gro or .pdb):", own_coords_row)

        self._own_topology_label = QLabel("No file selected")
        own_topology_button = QPushButton("Browse…")
        own_topology_button.clicked.connect(self._on_browse_own_topology_clicked)
        own_topology_row = QHBoxLayout()
        own_topology_row.addWidget(self._own_topology_label, 1)
        own_topology_row.addWidget(own_topology_button)
        bring_own_form.addRow("Topology file (.top, ready to use):", own_topology_row)

        self.form_layout.addRow(self._bring_own_container)

    @staticmethod
    def _new_subform(container: QWidget) -> QFormLayout:
        layout = QFormLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    # --- mode switching ---
    def _update_mode_visibility(self) -> None:
        generate_mode = self._generate_radio.isChecked()
        self._generate_container.setVisible(generate_mode)
        self._bring_own_container.setVisible(not generate_mode)

    # --- generate-mode fields ---
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

    def _on_browse_structure_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a structure file", str(Path.home()), "Structure files (*.pdb *.gro)"
        )
        if not path:
            return
        self._set_structure_path(Path(path))

    def _set_structure_path(self, path: Path) -> None:
        self._input_path = path
        self._input_label.setText(path.name)
        self._rebuild_residue_checklist()

    def _rebuild_residue_checklist(self) -> None:
        while self._residue_list_layout.count():
            item = self._residue_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._residue_checkboxes.clear()

        if self._input_path is None or self._input_path.suffix.lower() != ".pdb":
            self._cleanup_group.setVisible(False)
            return

        residues = list_heteroatom_residues(self._input_path)
        if not residues:
            self._cleanup_group.setVisible(False)
            return

        for name, count in sorted(residues.items()):
            checkbox = QCheckBox(f"{name} ×{count}")
            checkbox.setChecked(True)
            self._residue_list_layout.addWidget(checkbox)
            self._residue_checkboxes[name] = checkbox
        self._cleanup_group.setVisible(True)

    # --- bring-your-own-mode fields ---
    def _on_browse_own_coords_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a coordinate file", str(Path.home()), "Coordinate files (*.gro *.pdb)"
        )
        if not path:
            return
        self._own_coords_path = Path(path)
        self._own_coords_label.setText(self._own_coords_path.name)

    def _on_browse_own_topology_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a topology file", str(Path.home()), "Topology files (*.top)"
        )
        if not path:
            return
        self._own_topology_path = Path(path)
        self._own_topology_label.setText(self._own_topology_path.name)

    # --- StepBase overrides ---
    def is_valid(self) -> bool:
        if self._generate_radio.isChecked():
            return (
                self._input_path is not None
                and self._input_path.is_file()
                and self.force_field_combo.currentData() is not None
                and self.water_model_combo.currentData() is not None
            )
        return (
            self._own_coords_path is not None
            and self._own_coords_path.is_file()
            and self._own_topology_path is not None
            and self._own_topology_path.is_file()
        )

    def build_commands(self) -> list[StepCommand]:
        if self._generate_radio.isChecked():
            return self._build_generate_commands()
        self._stage_own_files()
        return []

    def _build_generate_commands(self) -> list[StepCommand]:
        assert self._input_path is not None
        structure_dir = self.project.step_dir(self.step_name)

        source_pdb = self._input_path
        residues_to_remove = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }
        if residues_to_remove:
            cleaned_pdb = structure_dir / "cleaned.pdb"
            remove_residues(source_pdb, cleaned_pdb, residues_to_remove)
            source_pdb = cleaned_pdb

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

    def _stage_own_files(self) -> None:
        assert self._own_coords_path is not None
        assert self._own_topology_path is not None
        structure_dir = self.project.step_dir(self.step_name)
        topology_dir = self.project.root / "topology"

        coords_dest = structure_dir / f"processed{self._own_coords_path.suffix.lower()}"
        shutil.copyfile(self._own_coords_path, coords_dest)
        topology_dest = topology_dir / conventions.TOPOLOGY_TOP
        shutil.copyfile(self._own_topology_path, topology_dest)

    def output_files(self) -> list[str]:
        root = self.project.root
        structure_dir = self.project.step_dir(self.step_name)
        topology_dir = root / "topology"

        if self._generate_radio.isChecked():
            return [
                str((structure_dir / conventions.STRUCTURE_GRO).relative_to(root)),
                str((topology_dir / conventions.TOPOLOGY_TOP).relative_to(root)),
                str((topology_dir / conventions.POSRE_ITP).relative_to(root)),
            ]

        assert self._own_coords_path is not None
        coords_dest = structure_dir / f"processed{self._own_coords_path.suffix.lower()}"
        topology_dest = topology_dir / conventions.TOPOLOGY_TOP
        return [str(coords_dest.relative_to(root)), str(topology_dest.relative_to(root))]
