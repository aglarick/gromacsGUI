from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import build_pdb2gmx_command
from gromacs_gui.gmx.forcefields import gmxdata_top_dir, list_force_fields, list_water_models
from gromacs_gui.gmx.topology import build_wrapping_topology, parse_moleculetype_name
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand

_WATER_MODEL_HELP_TEXT = (
    "El modelo de agua elegido aquí queda registrado en la topología, y el "
    "paso de solvatación usará por defecto una caja de agua compatible con él."
)

_SERVER_INFO_TEXT = (
    "Próximamente: esto abrirá una página para poner en cola la generación del "
    "campo de fuerza de tu molécula en un servidor dedicado, a partir de un "
    ".gro o .pdb ya limpio. Todavía no está disponible."
)

# Herramientas como LigParGen o ATB suelen generar su propia carpeta de campo
# de fuerza (p. ej. oplsaam.ff), distinta de los campos de fuerza que trae
# GROMACS de fábrica — seleccionar uno de los de fábrica no necesariamente
# es compatible con esos parámetros.
_CUSTOM_FF_SENTINEL = "__custom_ff__"


class StepStructureWidget(StepBase):
    step_name = "structure"

    DESCRIPTION = (
        "Prepara la molécula que vas a simular: a partir de un archivo de "
        "coordenadas, obtienes un .gro y una topología (los parámetros de "
        "campo de fuerza) listos para el resto del flujo. Si ya tienes ambos "
        "—por ejemplo, de ATB o LigParGen— puedes saltarte la generación e "
        "indicar directamente dónde están tus archivos. Si tu estructura trae "
        "aguas cristalográficas u otras moléculas que no quieres incluir, "
        "límpiala primero en el paso 'Limpieza'."
    )

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self._input_path: Path | None = None
        self._own_coords_path: Path | None = None
        self._own_topology_path: Path | None = None

        self._build_mode_selector()
        self._build_generate_section()
        self._build_bring_own_section()
        self._build_server_section()

        self._populate_force_field_combo(self.force_field_combo)
        self.force_field_combo.currentIndexChanged.connect(self._populate_water_models)
        self._populate_water_models()
        self._populate_force_field_combo(self._own_topology_ff_combo)
        self._own_topology_ff_combo.addItem(
            "Otra carpeta de campo de fuerza (.ff)…", userData=_CUSTOM_FF_SENTINEL
        )
        self._own_topology_ff_combo.currentIndexChanged.connect(
            self._update_custom_ff_row_visibility
        )
        self._update_custom_ff_row_visibility()

        for radio in (self._generate_radio, self._bring_own_radio, self._server_radio):
            radio.toggled.connect(self._update_mode_visibility)
        self._update_mode_visibility()

    # --- construction ---
    def _build_mode_selector(self) -> None:
        self._generate_radio = QRadioButton(
            "Generar topología con pdb2gmx (solo para proteínas, ácidos "
            "nucleicos u otras moléculas que el campo de fuerza ya reconoce — "
            "no es un generador general de campos de fuerza)"
        )
        self._bring_own_radio = QRadioButton(
            "Ya tengo estructura y topología (de ATB, LigParGen, u otra fuente)"
        )
        self._server_radio = QRadioButton("Generar campo de fuerza en el servidor (próximamente)")
        self._generate_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        for radio in (self._generate_radio, self._bring_own_radio, self._server_radio):
            mode_group.addButton(radio)

        mode_box = QWidget(self)
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(QLabel("¿Qué tienes?"))
        mode_layout.addWidget(self._generate_radio)
        mode_layout.addWidget(self._bring_own_radio)
        mode_layout.addWidget(self._server_radio)
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

        self.force_field_combo = QComboBox()
        self.water_model_combo = QComboBox()
        generate_form.addRow("Force field:", self.force_field_combo)
        generate_form.addRow("Water model:", self.water_model_combo)
        water_help_label = QLabel(_WATER_MODEL_HELP_TEXT)
        water_help_label.setWordWrap(True)
        generate_form.addRow(water_help_label)

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
        bring_own_form.addRow("Topology file (.top or .itp):", own_topology_row)

        self._own_topology_ff_combo = QComboBox()
        bring_own_form.addRow("Force field (solo si es .itp):", self._own_topology_ff_combo)

        self._own_custom_ff_path: Path | None = None
        self._own_custom_ff_label = QLabel("No folder selected")
        own_custom_ff_button = QPushButton("Browse…")
        own_custom_ff_button.clicked.connect(self._on_browse_custom_ff_clicked)
        own_custom_ff_row = QHBoxLayout()
        own_custom_ff_row.addWidget(self._own_custom_ff_label, 1)
        own_custom_ff_row.addWidget(own_custom_ff_button)
        self._own_custom_ff_container = QWidget()
        self._own_custom_ff_container.setLayout(own_custom_ff_row)
        bring_own_form.addRow("Carpeta .ff personalizada:", self._own_custom_ff_container)

        itp_help_label = QLabel(
            "Si eliges un .itp, construimos el .top que lo envuelve incluyendo "
            "el campo de fuerza que elijas aquí. Si tu generador (LigParGen, "
            "ATB, u otro) trae su propia carpeta de campo de fuerza en vez de "
            "usar una de las que trae GROMACS, elige 'Otra carpeta de campo de "
            "fuerza (.ff)…' y selecciónala — no asumas que un campo de fuerza "
            "de la lista es compatible con parámetros generados externamente. "
            "Si ya tienes un .top completo, nada de esto se usa."
        )
        itp_help_label.setWordWrap(True)
        bring_own_form.addRow(itp_help_label)

        self.form_layout.addRow(self._bring_own_container)

    def _build_server_section(self) -> None:
        self._server_container = QWidget(self)
        server_layout = QVBoxLayout(self._server_container)
        server_layout.setContentsMargins(0, 0, 0, 0)
        info_label = QLabel(_SERVER_INFO_TEXT)
        info_label.setWordWrap(True)
        server_layout.addWidget(info_label)
        self.form_layout.addRow(self._server_container)

    @staticmethod
    def _new_subform(container: QWidget) -> QFormLayout:
        layout = QFormLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    # --- mode switching ---
    def _update_mode_visibility(self) -> None:
        generate_mode = self._generate_radio.isChecked()
        bring_own_mode = self._bring_own_radio.isChecked()
        server_mode = self._server_radio.isChecked()

        self._generate_container.setVisible(generate_mode)
        self._bring_own_container.setVisible(bring_own_mode)
        self._server_container.setVisible(server_mode)
        self.run_button.setEnabled(not server_mode)

    # --- generate-mode fields ---
    def _populate_force_field_combo(self, combo: QComboBox) -> None:
        top_dir = gmxdata_top_dir(self.gmx_env)
        if top_dir is None:
            return
        for ff in list_force_fields(top_dir):
            combo.addItem(f"{ff.name} — {ff.description}", userData=ff.name)

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
            self, "Select a topology file", str(Path.home()), "Topology files (*.top *.itp)"
        )
        if not path:
            return
        self._own_topology_path = Path(path)
        self._own_topology_label.setText(self._own_topology_path.name)

    def _update_custom_ff_row_visibility(self) -> None:
        is_custom = self._own_topology_ff_combo.currentData() == _CUSTOM_FF_SENTINEL
        self._own_custom_ff_container.setVisible(is_custom)

    def _on_browse_custom_ff_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select a force field folder (<name>.ff)", str(Path.home())
        )
        if not folder:
            return
        self._own_custom_ff_path = Path(folder)
        self._own_custom_ff_label.setText(self._own_custom_ff_path.name)

    # --- StepBase overrides ---
    def is_valid(self) -> bool:
        if self._generate_radio.isChecked():
            return (
                self._input_path is not None
                and self._input_path.is_file()
                and self.force_field_combo.currentData() is not None
                and self.water_model_combo.currentData() is not None
            )
        if self._bring_own_radio.isChecked():
            topology_ready = (
                self._own_topology_path is not None
                and self._own_topology_path.is_file()
                and (
                    self._own_topology_path.suffix.lower() != ".itp"
                    or self._itp_force_field_ready()
                )
            )
            return (
                self._own_coords_path is not None
                and self._own_coords_path.is_file()
                and topology_ready
            )
        return False  # server mode: not available yet

    def _itp_force_field_ready(self) -> bool:
        data = self._own_topology_ff_combo.currentData()
        if data is None:
            return False
        if data == _CUSTOM_FF_SENTINEL:
            return (
                self._own_custom_ff_path is not None
                and (self._own_custom_ff_path / "forcefield.itp").is_file()
            )
        return True

    def build_commands(self) -> list[StepCommand]:
        if self._generate_radio.isChecked():
            return self._build_generate_commands()
        self._stage_own_files()
        return []

    def _build_generate_commands(self) -> list[StepCommand]:
        assert self._input_path is not None
        structure_dir = self.project.step_dir(self.step_name)

        force_field = self.force_field_combo.currentData()
        water_model = self.water_model_combo.currentData()
        self.project.manifest.force_field = force_field
        self.project.manifest.water_model = water_model

        topology_dir = self.project.root / "topology"
        args = build_pdb2gmx_command(
            self._input_path,
            structure_dir / conventions.STRUCTURE_GRO,
            topology_dir / conventions.TOPOLOGY_TOP,
            topology_dir / conventions.POSRE_ITP,
            force_field,
            water_model,
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
        if self._own_topology_path.suffix.lower() == ".itp":
            force_field = self._resolve_itp_force_field(topology_dir)
            itp_dest = topology_dir / self._own_topology_path.name
            shutil.copyfile(self._own_topology_path, itp_dest)
            molecule_name = parse_moleculetype_name(itp_dest)
            topology_dest.write_text(
                build_wrapping_topology(itp_dest.name, force_field, molecule_name)
            )
        else:
            shutil.copyfile(self._own_topology_path, topology_dest)

    def _resolve_itp_force_field(self, topology_dir: Path) -> str:
        """Return the bare force field name to `#include` for the .itp, copying
        a user-supplied custom .ff folder into the project first if that's
        what was chosen (rather than assuming a GROMACS-bundled one applies).
        """
        data = self._own_topology_ff_combo.currentData()
        if data != _CUSTOM_FF_SENTINEL:
            return data

        assert self._own_custom_ff_path is not None
        dest_name = self._own_custom_ff_path.name
        if not dest_name.endswith(".ff"):
            dest_name += ".ff"
        dest_dir = topology_dir / dest_name
        if not dest_dir.exists():
            shutil.copytree(self._own_custom_ff_path, dest_dir)
        return dest_name.removesuffix(".ff")

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
