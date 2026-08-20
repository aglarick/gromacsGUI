from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import build_pdb2gmx_command
from gromacs_gui.gmx.forcefields import (
    gmxdata_top_dir,
    list_force_fields,
    list_recognized_residues,
    list_water_models,
)
from gromacs_gui.gmx.structure_files import list_residues
from gromacs_gui.gmx.topology import (
    build_combined_topology,
    extract_generated_topology_chunk,
    parse_moleculetype_name,
    parse_moleculetype_name_from_text,
    rename_moleculetype,
    rename_posre_include,
)
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand

# Tools like LigParGen or ATB often generate their own force field folder
# (e.g. oplsaam.ff), distinct from GROMACS's bundled ones - picking a
# bundled one isn't necessarily compatible with those parameters.
_CUSTOM_FF_SENTINEL = "__custom_ff__"
_NO_WATER_SENTINEL = "none"

_STEP_DESCRIPTION = (
    "Gather the structure and topology for every molecule your system needs "
    "and combine them into one topology. Add one row per molecule (protein, "
    "ligand, cofactor, ...). For each, load a coordinate file: if the force "
    "field chosen below recognizes all of its residues, it's generated "
    "automatically with pdb2gmx; otherwise, provide its .itp (e.g. from ATB "
    "or LigParGen). This step only checks that the pieces fit together — it "
    "doesn't build the actual simulation box yet (that's Box, step 2) or "
    "verify the force fields truly work together (a later step). If your "
    "structure carries crystallographic water or other molecules you don't "
    "want, clean it first in the 'Cleanup' step."
)

_MASTER_TOP_DESCRIPTION = (
    "If you already have a complete .top covering every molecule in your "
    "system, you can provide it here instead of generating one. When set, "
    "it's used as-is and the force field/water model/per-row topology "
    "options below are ignored - each row then only needs a coordinate file."
)


class _MoleculeRow(QWidget):
    """One molecule: its coordinate file, and (unless a master .top makes
    this moot) how to get its topology - generated with pdb2gmx if the
    step's chosen force field recognizes every residue in the file,
    otherwise a user-supplied .itp.
    """

    def __init__(self, step: StepStructureWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.step = step
        self.structure_path: Path | None = None
        self.itp_path: Path | None = None
        self.custom_ff_path: Path | None = None
        self.recognized = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(form)

        self.structure_label = QLabel("No file selected")
        structure_button = QPushButton("Browse…")
        structure_button.clicked.connect(self._on_browse_structure_clicked)
        structure_row = QHBoxLayout()
        structure_row.addWidget(self.structure_label, 1)
        structure_row.addWidget(structure_button)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._on_remove_clicked)
        structure_row.addWidget(remove_button)
        form.addRow("Coordinate file (.gro/.pdb):", structure_row)

        self.recognition_label = QLabel("")
        self.recognition_label.setWordWrap(True)
        form.addRow(self.recognition_label)

        self.itp_label = QLabel("No file selected")
        itp_button = QPushButton("Browse…")
        itp_button.clicked.connect(self._on_browse_itp_clicked)
        itp_row = QHBoxLayout()
        itp_row.addWidget(self.itp_label, 1)
        itp_row.addWidget(itp_button)
        self.itp_field_label = QLabel("Topology (.itp, optional if you gave a master .top):")
        form.addRow(self.itp_field_label, itp_row)

        self.itp_ff_combo = QComboBox()
        self.itp_ff_combo.currentIndexChanged.connect(self._update_custom_ff_row_visibility)
        self.itp_ff_label = QLabel("Force field for this .itp:")
        form.addRow(self.itp_ff_label, self.itp_ff_combo)

        self.custom_ff_label = QLabel("No folder selected")
        custom_ff_button = QPushButton("Browse…")
        custom_ff_button.clicked.connect(self._on_browse_custom_ff_clicked)
        custom_ff_row = QHBoxLayout()
        custom_ff_row.addWidget(self.custom_ff_label, 1)
        custom_ff_row.addWidget(custom_ff_button)
        self.custom_ff_field_label = QLabel("Custom .ff folder:")
        form.addRow(self.custom_ff_field_label, custom_ff_row)

        self._populate_itp_ff_combo()
        self.set_master_top_mode(False)

    def _populate_itp_ff_combo(self) -> None:
        self.itp_ff_combo.clear()
        top_dir = gmxdata_top_dir(self.step.gmx_env)
        if top_dir is not None:
            for ff in list_force_fields(top_dir):
                self.itp_ff_combo.addItem(f"{ff.name} — {ff.description}", userData=ff.name)
        self.itp_ff_combo.addItem("Other custom .ff folder…", userData=_CUSTOM_FF_SENTINEL)
        self._update_custom_ff_row_visibility()

    def _on_browse_structure_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a coordinate file", str(Path.home()), "Structure files (*.pdb *.gro)"
        )
        if not path:
            return
        self.structure_path = Path(path)
        self.structure_label.setText(self.structure_path.name)
        self._update_recognition()

    def _on_remove_clicked(self) -> None:
        self.step.remove_row(self)

    def _on_browse_itp_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a topology fragment", str(Path.home()), "Topology files (*.itp)"
        )
        if not path:
            return
        self.itp_path = Path(path)
        self.itp_label.setText(self.itp_path.name)

    def _update_custom_ff_row_visibility(self) -> None:
        is_custom = self.itp_ff_combo.currentData() == _CUSTOM_FF_SENTINEL
        self.custom_ff_field_label.setVisible(is_custom)
        self.custom_ff_label.setVisible(is_custom)

    def _on_browse_custom_ff_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select a force field folder (<name>.ff)", str(Path.home())
        )
        if not folder:
            return
        self.custom_ff_path = Path(folder)
        self.custom_ff_label.setText(self.custom_ff_path.name)

    def set_master_top_mode(self, enabled: bool) -> None:
        self.recognition_label.setVisible(not enabled)
        self.itp_field_label.setVisible(not enabled)
        self.itp_label.setVisible(not enabled)
        visible_and_custom = (not enabled) and self.itp_ff_combo.currentData() == (
            _CUSTOM_FF_SENTINEL
        )
        self.itp_ff_label.setVisible(not enabled)
        self.itp_ff_combo.setVisible(not enabled)
        self.custom_ff_field_label.setVisible(visible_and_custom)
        self.custom_ff_label.setVisible(visible_and_custom)
        if not enabled:
            self._update_recognition()

    def _update_recognition(self) -> None:
        if self.structure_path is None:
            self.recognized = False
            self.recognition_label.setText("")
            return
        residue_names = set(list_residues(self.structure_path))
        recognized_db = self.step.recognized_residues()
        self.recognized = bool(residue_names) and residue_names <= recognized_db
        if self.recognized:
            self.recognition_label.setText(
                f"✓ Recognized by {self.step.chosen_force_field()} — will generate with pdb2gmx."
            )
        else:
            self.recognition_label.setText(
                "Not recognized by the chosen force field — provide its topology (.itp) below."
            )

    def is_valid(self, master_top_mode: bool) -> bool:
        if self.structure_path is None or not self.structure_path.is_file():
            return False
        if master_top_mode:
            return True
        if self.recognized:
            return True
        return self.itp_path is not None and self.itp_path.is_file() and self._itp_ff_ready()

    def _itp_ff_ready(self) -> bool:
        data = self.itp_ff_combo.currentData()
        if data is None:
            return False
        if data == _CUSTOM_FF_SENTINEL:
            return (
                self.custom_ff_path is not None
                and (self.custom_ff_path / "forcefield.itp").is_file()
            )
        return True

    def resolved_ff_name(self) -> str:
        """Bare force field name (no .ff suffix) to #include for this row's
        .itp, copying a custom folder into the project first if needed.
        """
        data = self.itp_ff_combo.currentData()
        if data != _CUSTOM_FF_SENTINEL:
            return data

        assert self.custom_ff_path is not None
        topology_dir = self.step.project.root / "topology"
        dest_name = self.custom_ff_path.name
        if not dest_name.endswith(".ff"):
            dest_name += ".ff"
        dest_dir = topology_dir / dest_name
        if not dest_dir.exists():
            shutil.copytree(self.custom_ff_path, dest_dir)
        return dest_name.removesuffix(".ff")


class StepStructureWidget(StepBase):
    step_name = "structure"

    DESCRIPTION = _STEP_DESCRIPTION

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self._rows: list[_MoleculeRow] = []
        self._recognized_residues_cache: dict[str, set[str]] = {}

        self.force_field_combo = QComboBox()
        self._populate_force_field_combo()
        self.force_field_combo.currentIndexChanged.connect(self._on_force_field_changed)
        self.form_layout.addRow("Force field:", self.force_field_combo)

        self.water_model_combo = QComboBox()
        self._populate_water_models()
        self.form_layout.addRow("Water model:", self.water_model_combo)

        master_top_label = QLabel(_MASTER_TOP_DESCRIPTION)
        master_top_label.setWordWrap(True)
        self.form_layout.addRow(master_top_label)

        self._master_top_path: Path | None = None
        self.master_top_label = QLabel("No file selected")
        master_top_button = QPushButton("Browse…")
        master_top_button.clicked.connect(self._on_browse_master_top_clicked)
        clear_master_top_button = QPushButton("Clear")
        clear_master_top_button.clicked.connect(self._on_clear_master_top_clicked)
        master_top_row = QHBoxLayout()
        master_top_row.addWidget(self.master_top_label, 1)
        master_top_row.addWidget(master_top_button)
        master_top_row.addWidget(clear_master_top_button)
        self.form_layout.addRow("Master .top (optional):", master_top_row)

        add_row_button = QPushButton("Add molecule")
        add_row_button.clicked.connect(self.add_row)
        self.form_layout.addRow(add_row_button)

        self._rows_layout = QVBoxLayout()
        self.form_layout.addRow(self._rows_layout)

        self.add_row()

    # --- force field / water model ---
    def _populate_force_field_combo(self) -> None:
        top_dir = gmxdata_top_dir(self.gmx_env)
        if top_dir is None:
            return
        for ff in list_force_fields(top_dir):
            self.force_field_combo.addItem(f"{ff.name} — {ff.description}", userData=ff.name)

    def _populate_water_models(self) -> None:
        self.water_model_combo.clear()
        self.water_model_combo.addItem("None (no water)", userData=_NO_WATER_SENTINEL)
        top_dir = gmxdata_top_dir(self.gmx_env)
        force_field = self.force_field_combo.currentData()
        if top_dir is None or not force_field:
            return
        for model in list_water_models(top_dir, force_field):
            self.water_model_combo.addItem(
                f"{model.name} — {model.description}", userData=model.name
            )

    def _on_force_field_changed(self) -> None:
        self._populate_water_models()
        for row in self._rows:
            row._update_recognition()

    def chosen_force_field(self) -> str | None:
        return self.force_field_combo.currentData()

    def recognized_residues(self) -> set[str]:
        ff = self.chosen_force_field()
        if not ff:
            return set()
        if ff not in self._recognized_residues_cache:
            top_dir = gmxdata_top_dir(self.gmx_env)
            self._recognized_residues_cache[ff] = (
                list_recognized_residues(top_dir, ff) if top_dir is not None else set()
            )
        return self._recognized_residues_cache[ff]

    # --- master .top ---
    def _on_browse_master_top_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a complete topology", str(Path.home()), "Topology files (*.top)"
        )
        if not path:
            return
        self._master_top_path = Path(path)
        self.master_top_label.setText(self._master_top_path.name)
        self._update_master_top_mode()

    def _on_clear_master_top_clicked(self) -> None:
        self._master_top_path = None
        self.master_top_label.setText("No file selected")
        self._update_master_top_mode()

    def _update_master_top_mode(self) -> None:
        enabled = self._master_top_path is not None
        self.force_field_combo.setEnabled(not enabled)
        self.water_model_combo.setEnabled(not enabled)
        for row in self._rows:
            row.set_master_top_mode(enabled)

    # --- rows ---
    def add_row(self) -> None:
        row = _MoleculeRow(self, self)
        row.set_master_top_mode(self._master_top_path is not None)
        self._rows.append(row)
        self._rows_layout.addWidget(row)

    def remove_row(self, row: _MoleculeRow) -> None:
        if len(self._rows) <= 1:
            return  # always keep at least one row
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    # --- StepBase overrides ---
    def is_valid(self) -> bool:
        master_top_mode = self._master_top_path is not None
        if master_top_mode and not self._master_top_path.is_file():
            return False
        if not self._rows:
            return False
        if not master_top_mode and not self.chosen_force_field():
            return False
        return all(row.is_valid(master_top_mode) for row in self._rows)

    def build_commands(self) -> list[StepCommand]:
        if self._master_top_path is not None:
            self._stage_master_top()
            return []

        commands: list[StepCommand] = []
        self._pdb2gmx_row_indices: list[int] = []
        for i, row in enumerate(self._rows):
            if row.recognized:
                commands.append(self._build_pdb2gmx_command(i, row))
                self._pdb2gmx_row_indices.append(i)
        return commands

    def _build_pdb2gmx_command(self, index: int, row: _MoleculeRow) -> StepCommand:
        assert row.structure_path is not None
        mol_dir = self.project.step_dir(self.step_name) / f"mol_{index}"
        mol_dir.mkdir(parents=True, exist_ok=True)

        force_field = self.chosen_force_field()
        water_model = self.water_model_combo.currentData()
        self.project.manifest.force_field = force_field
        self.project.manifest.water_model = (
            None if water_model == _NO_WATER_SENTINEL else (water_model)
        )

        args = build_pdb2gmx_command(
            row.structure_path,
            mol_dir / "processed.gro",
            mol_dir / "topol.top",
            mol_dir / "posre.itp",
            force_field,
            water_model,
        )
        return StepCommand(args=args)

    def on_all_commands_finished(self) -> None:
        if self._master_top_path is not None:
            return
        self._combine_topologies()

    def _combine_topologies(self) -> None:
        topology_dir = self.project.root / "topology"
        topology_dir.mkdir(parents=True, exist_ok=True)
        force_field_includes: dict[str, str] = {}
        molecule_chunks: list[str] = []
        molecules: list[tuple[str, int]] = []
        used_names: set[str] = set()

        chosen_ff = self.chosen_force_field()
        if chosen_ff:
            force_field_includes[chosen_ff] = f'#include "{chosen_ff}.ff/forcefield.itp"\n'

        first_pdb2gmx_seen = False
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            structure_dir = self.project.step_dir(self.step_name)

            if row.recognized:
                mol_dir = structure_dir / f"mol_{i}"
                gro_dest = structure_dir / f"mol_{i}.gro"
                shutil.copyfile(mol_dir / "processed.gro", gro_dest)

                chunk = extract_generated_topology_chunk(
                    mol_dir / "topol.top", include_water_and_ions=not first_pdb2gmx_seen
                )
                first_pdb2gmx_seen = True

                posre_dest_name = f"posre_mol{i}.itp"
                shutil.copyfile(mol_dir / "posre.itp", topology_dir / posre_dest_name)
                chunk = rename_posre_include(chunk, "posre.itp", posre_dest_name)

                original_name = parse_moleculetype_name_from_text(chunk)
                name = self._unique_name(original_name, used_names)
                if name != original_name:
                    chunk = rename_moleculetype(chunk, name)
            else:
                gro_dest = structure_dir / f"mol_{i}{row.structure_path.suffix.lower()}"
                shutil.copyfile(row.structure_path, gro_dest)

                assert row.itp_path is not None
                ff_name = row.resolved_ff_name()
                force_field_includes.setdefault(
                    ff_name, f'#include "{ff_name}.ff/forcefield.itp"\n'
                )
                itp_dest = topology_dir / row.itp_path.name
                shutil.copyfile(row.itp_path, itp_dest)
                name = self._unique_name(parse_moleculetype_name(itp_dest), used_names)
                chunk = f'#include "{itp_dest.name}"\n'

            used_names.add(name)
            molecule_chunks.append(chunk)
            molecules.append((name, 1))

        combined = build_combined_topology(
            force_field_includes=list(force_field_includes.values()),
            molecule_chunks=molecule_chunks,
            molecules=molecules,
        )
        (topology_dir / "topol.top").write_text(combined)

    @staticmethod
    def _unique_name(name: str, used_names: set[str]) -> str:
        if name not in used_names:
            return name
        suffix = 2
        while f"{name}_{suffix}" in used_names:
            suffix += 1
        return f"{name}_{suffix}"

    def _stage_master_top(self) -> None:
        assert self._master_top_path is not None
        topology_dir = self.project.root / "topology"
        topology_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._master_top_path, topology_dir / "topol.top")

        structure_dir = self.project.step_dir(self.step_name)
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            dest = structure_dir / f"mol_{i}{row.structure_path.suffix.lower()}"
            shutil.copyfile(row.structure_path, dest)

    def output_files(self) -> list[str]:
        root = self.project.root
        structure_dir = self.project.step_dir(self.step_name)
        files = [str((root / "topology" / "topol.top").relative_to(root))]
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            suffix = "gro" if row.recognized else row.structure_path.suffix.lower().lstrip(".")
            path = structure_dir / f"mol_{i}.{suffix}"
            if path.is_file():
                files.append(str(path.relative_to(root)))
        return files
