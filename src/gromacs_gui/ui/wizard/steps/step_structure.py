from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core import conventions
from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import STEP_ORDER
from gromacs_gui.gmx.commands.grompp import build_grompp_command
from gromacs_gui.gmx.commands.pdb2gmx import build_pdb2gmx_command
from gromacs_gui.gmx.forcefields import (
    gmxdata_top_dir,
    list_force_fields,
    list_water_models,
    list_water_models_in_folder,
)
from gromacs_gui.gmx.structure_files import AtomPosition, read_atom_positions, write_gro
from gromacs_gui.gmx.topology import (
    build_combined_topology,
    extract_generated_topology_chunk,
    parse_moleculetype_name,
    parse_moleculetype_name_from_text,
    rename_moleculetype,
    rename_posre_include,
)
from gromacs_gui.mdp.defaults import default_mdp_path
from gromacs_gui.ui.wizard.step_base import StepBase, StepCommand
from gromacs_gui.utils.settings import find_gmx_binary

# Padding (nm) added around the bounding box of every row's raw coordinates
# to build a synthetic box just large enough for grompp's consistency check
# (Verlet cutoffs need the box edge to clear 2x the cutoff radius) - this is
# not a real simulation box, just enough for grompp to preprocess the
# topology without erroring on box size.
_VERIFICATION_BOX_PADDING_NM = 2.0
_VERIFICATION_MIN_BOX_NM = 3.0

# Tools like LigParGen or ATB often generate their own force field folder
# (e.g. oplsaam.ff), distinct from GROMACS's bundled ones - picking a
# bundled one isn't necessarily compatible with those parameters.
_CUSTOM_FF_SENTINEL = "__custom_ff__"
_NO_WATER_SENTINEL = "none"

_STEP_DESCRIPTION = (
    "Gather the structure and topology for every molecule your system needs, "
    "all sharing one force field, and combine them into one topology. Add "
    "one row per molecule (protein, ligand, cofactor, ...): a coordinate "
    "file is required, and a .itp is optional - leave it out to generate "
    "that molecule with pdb2gmx using the force field chosen below (this "
    "only works with a bundled force field, not a custom folder). This step "
    "only checks that the pieces fit together - it doesn't build the actual "
    "simulation box yet (that's Box, step 2) or verify the force fields "
    "truly work together (a later step). If your structure carries "
    "crystallographic water or other molecules you don't want, clean it "
    "first in the 'Cleanup' tool."
)


class _MoleculeRow(QWidget):
    """One molecule: a coordinate file (required) and an optional .itp. All
    molecules are assumed to share the step's one chosen force field, so
    there's nothing else to ask per row - leaving .itp empty means "generate
    this one with pdb2gmx".
    """

    def __init__(self, step: StepStructureWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.step = step
        self.structure_path: Path | None = None
        self.itp_path: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)

        row = QHBoxLayout()
        outer.addLayout(row)

        row.addWidget(QLabel("Coordinates:"))
        self.structure_label = QLabel("No file selected")
        row.addWidget(self.structure_label, 1)
        structure_button = QPushButton("Browse…")
        structure_button.clicked.connect(self._on_browse_structure_clicked)
        row.addWidget(structure_button)

        row.addSpacing(16)

        row.addWidget(QLabel("Topology .itp (optional):"))
        self.itp_label = QLabel("None — will generate with pdb2gmx")
        row.addWidget(self.itp_label, 1)
        itp_button = QPushButton("Browse…")
        itp_button.clicked.connect(self._on_browse_itp_clicked)
        row.addWidget(itp_button)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._on_remove_clicked)
        row.addWidget(remove_button)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b00;")
        self.error_label.setVisible(False)
        outer.addWidget(self.error_label)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(separator)

    def _on_browse_structure_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a coordinate file", str(Path.home()), "Structure files (*.pdb *.gro)"
        )
        if not path:
            return
        self.structure_path = Path(path)
        self.structure_label.setText(self.structure_path.name)
        self.step.refresh_row_validity()

    def _on_browse_itp_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a topology fragment", str(Path.home()), "Topology files (*.itp)"
        )
        if not path:
            return
        self.itp_path = Path(path)
        self.itp_label.setText(self.itp_path.name)
        self.step.refresh_row_validity()

    def _on_remove_clicked(self) -> None:
        self.step.remove_row(self)

    def is_valid(self) -> bool:
        if self.structure_path is None or not self.structure_path.is_file():
            self.error_label.setVisible(False)
            return False
        if self.itp_path is not None:
            self.error_label.setVisible(False)
            return self.itp_path.is_file()
        if self.step.force_field_is_custom():
            self.error_label.setText(
                "This molecule needs a .itp — pdb2gmx generation isn't "
                "available with a custom force field folder."
            )
            self.error_label.setVisible(True)
            return False
        self.error_label.setVisible(False)
        return True


class StepStructureWidget(StepBase):
    step_name = "structure"

    DESCRIPTION = _STEP_DESCRIPTION
    RUN_BUTTON_LABEL = "Test system"

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(project, gmx_env, parent)

        self._rows: list[_MoleculeRow] = []
        self._custom_ff_path: Path | None = None

        self.force_field_combo = QComboBox()
        self._populate_force_field_combo()
        self.force_field_combo.currentIndexChanged.connect(self._on_force_field_changed)
        self.form_layout.addRow("Force field:", self.force_field_combo)

        self._custom_ff_label = QLabel("No folder selected")
        self._custom_ff_button = QPushButton("Browse…")
        self._custom_ff_button.clicked.connect(self._on_browse_custom_ff_clicked)
        custom_ff_row = QHBoxLayout()
        custom_ff_row.addWidget(self._custom_ff_label, 1)
        custom_ff_row.addWidget(self._custom_ff_button)
        self._custom_ff_field_label = QLabel("Custom .ff folder:")
        self.form_layout.addRow(self._custom_ff_field_label, custom_ff_row)

        self.water_model_combo = QComboBox()
        self.form_layout.addRow("Water model (optional):", self.water_model_combo)
        self._populate_water_models()

        self._update_custom_ff_row_visibility()

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.form_layout.addRow(separator)

        self._rows_layout = QVBoxLayout()
        self.form_layout.addRow(self._rows_layout)

        self._add_row_button = QPushButton("Add molecule")
        self._add_row_button.clicked.connect(self.add_row)
        self._rows_layout.addWidget(self._add_row_button)

        self.add_row()

    # --- force field / water model ---
    def _populate_force_field_combo(self) -> None:
        top_dir = gmxdata_top_dir(self.gmx_env)
        if top_dir is not None:
            for ff in list_force_fields(top_dir):
                self.force_field_combo.addItem(f"{ff.name} — {ff.description}", userData=ff.name)
        self.force_field_combo.addItem("Custom .ff folder…", userData=_CUSTOM_FF_SENTINEL)

    def _update_custom_ff_row_visibility(self) -> None:
        is_custom = self.force_field_is_custom()
        self._custom_ff_field_label.setVisible(is_custom)
        self._custom_ff_label.setVisible(is_custom)
        self._custom_ff_button.setVisible(is_custom)

    def _on_force_field_changed(self) -> None:
        self._update_custom_ff_row_visibility()
        self._populate_water_models()
        self.refresh_row_validity()

    def _on_browse_custom_ff_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select a force field folder (<name>.ff)", str(Path.home())
        )
        if not folder:
            return
        self._custom_ff_path = Path(folder)
        self._custom_ff_label.setText(self._custom_ff_path.name)
        self._populate_water_models()
        self.refresh_row_validity()

    def force_field_is_custom(self) -> bool:
        return self.force_field_combo.currentData() == _CUSTOM_FF_SENTINEL

    def _populate_water_models(self) -> None:
        self.water_model_combo.clear()
        self.water_model_combo.addItem("None (no water)", userData=_NO_WATER_SENTINEL)

        if self.force_field_is_custom():
            if self._custom_ff_path is not None:
                for model in list_water_models_in_folder(self._custom_ff_path):
                    self.water_model_combo.addItem(
                        f"{model.name} — {model.description}", userData=model.name
                    )
            return

        top_dir = gmxdata_top_dir(self.gmx_env)
        ff_name = self.force_field_combo.currentData()
        if top_dir is None or not ff_name:
            return
        for model in list_water_models(top_dir, ff_name):
            self.water_model_combo.addItem(
                f"{model.name} — {model.description}", userData=model.name
            )

    def _resolved_force_field_name(self) -> str | None:
        """Bare force field name (no .ff suffix) to pass to pdb2gmx's -ff /
        #include, copying a custom folder into the project first if needed.
        """
        if not self.force_field_is_custom():
            return self.force_field_combo.currentData()
        if self._custom_ff_path is None:
            return None
        topology_dir = self.project.root / "topology"
        topology_dir.mkdir(parents=True, exist_ok=True)
        dest_name = self._custom_ff_path.name
        if not dest_name.endswith(".ff"):
            dest_name += ".ff"
        dest_dir = topology_dir / dest_name
        if not dest_dir.exists():
            shutil.copytree(self._custom_ff_path, dest_dir)
        return dest_name.removesuffix(".ff")

    # --- rows ---
    def add_row(self) -> None:
        row = _MoleculeRow(self, self)
        self._rows.append(row)
        # Keep "Add molecule" pinned as the last widget, below every row.
        insert_index = self._rows_layout.indexOf(self._add_row_button)
        self._rows_layout.insertWidget(insert_index, row)

    def remove_row(self, row: _MoleculeRow) -> None:
        if len(self._rows) <= 1:
            return  # always keep at least one row
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    def refresh_row_validity(self) -> None:
        for row in self._rows:
            row.is_valid()  # updates each row's own inline error message

    # --- StepBase overrides ---
    def is_valid(self) -> bool:
        if not self._rows:
            return False
        if not self.force_field_combo.currentData():
            return False
        if self.force_field_is_custom() and self._custom_ff_path is None:
            return False
        return all(row.is_valid() for row in self._rows)

    def build_commands(self) -> list[StepCommand]:
        commands: list[StepCommand] = []
        for i, row in enumerate(self._rows):
            if row.itp_path is None:
                commands.append(self._build_pdb2gmx_command(i, row))
        return commands

    def _build_pdb2gmx_command(self, index: int, row: _MoleculeRow) -> StepCommand:
        assert row.structure_path is not None
        mol_dir = self.project.step_dir(self.step_name) / f"mol_{index}"
        mol_dir.mkdir(parents=True, exist_ok=True)

        force_field = self._resolved_force_field_name()
        water_model = self.water_model_combo.currentData()
        self.project.manifest.force_field = force_field
        self.project.manifest.water_model = (
            None if water_model == _NO_WATER_SENTINEL else water_model
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
        self._combine_topologies()

    def _combine_topologies(self) -> None:
        topology_dir = self.project.root / "topology"
        topology_dir.mkdir(parents=True, exist_ok=True)
        force_field_includes: dict[str, str] = {}
        molecule_chunks: list[str] = []
        molecules: list[tuple[str, int]] = []
        used_names: set[str] = set()

        chosen_ff = self._resolved_force_field_name()
        if chosen_ff:
            force_field_includes[chosen_ff] = f'#include "{chosen_ff}.ff/forcefield.itp"\n'

        first_pdb2gmx_seen = False
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            structure_dir = self.project.step_dir(self.step_name)

            if row.itp_path is None:
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

    def output_files(self) -> list[str]:
        root = self.project.root
        structure_dir = self.project.step_dir(self.step_name)
        files = [str((root / "topology" / "topol.top").relative_to(root))]
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            suffix = (
                "gro" if row.itp_path is None else row.structure_path.suffix.lower().lstrip(".")
            )
            path = structure_dir / f"mol_{i}.{suffix}"
            if path.is_file():
                files.append(str(path.relative_to(root)))
        combined_gro = structure_dir / conventions.STRUCTURE_GRO
        if combined_gro.is_file():
            files.append(str(combined_gro.relative_to(root)))
        return files

    # --- grompp consistency check (runs after on_all_commands_finished) ---
    def verify_before_finish(self) -> None:
        self._run_grompp_check()

    def _run_grompp_check(self) -> None:
        structure_dir = self.project.step_dir(self.step_name)
        combined_gro = self._write_combined_structure_gro(structure_dir)
        topology_top = self.project.root / "topology" / conventions.TOPOLOGY_TOP
        check_tpr = structure_dir / "consistency_check.tpr"

        args = build_grompp_command(
            default_mdp_path("ions"),
            combined_gro,
            topology_top,
            check_tpr,
            maxwarn=1,
        )
        gmx_path = find_gmx_binary(self.gmx_env) or "gmx"
        result = subprocess.run(
            [gmx_path, *args],
            cwd=str(self.project.root),
            env=self.gmx_env,
            capture_output=True,
            text=True,
        )
        stream = "stdout" if result.returncode == 0 else "stderr"
        for line in (result.stdout + result.stderr).splitlines():
            self.log_console.append_line(line, stream)

        if result.returncode != 0:
            self._prompt_inconsistent_system()
            raise RuntimeError("grompp reported an inconsistent system")

        if self._prompt_accept_system():
            self._request_next_step()

    def _write_combined_structure_gro(self, structure_dir: Path) -> Path:
        """Concatenate every row's already-copied mol_<i>.* coordinates into
        one combined structure/processed.gro, matching the [molecules] list
        (count 1 each) that _combine_topologies() just wrote - grompp needs
        one coordinate file whose atom order/count matches the topology, and
        this also happens to be the conventional single-file output Box
        (step 2) already expects.
        """
        combined_atoms: list[AtomPosition] = []
        for i, row in enumerate(self._rows):
            assert row.structure_path is not None
            suffix = (
                "gro" if row.itp_path is None else row.structure_path.suffix.lower().lstrip(".")
            )
            mol_path = structure_dir / f"mol_{i}.{suffix}"
            atoms = read_atom_positions(mol_path)
            combined_atoms.extend(
                replace(atom, instance_key=f"row{i}:{atom.instance_key}") for atom in atoms
            )

        combined_gro = structure_dir / conventions.STRUCTURE_GRO
        write_gro(combined_gro, combined_atoms, self._verification_box(combined_atoms))
        return combined_gro

    @staticmethod
    def _verification_box(atoms: list[AtomPosition]) -> tuple[float, float, float]:
        if not atoms:
            return (_VERIFICATION_MIN_BOX_NM, _VERIFICATION_MIN_BOX_NM, _VERIFICATION_MIN_BOX_NM)
        pad = _VERIFICATION_BOX_PADDING_NM

        def dim(values: list[float]) -> float:
            return max((max(values) - min(values)) / 10 + pad, _VERIFICATION_MIN_BOX_NM)

        return (
            dim([a.x for a in atoms]),
            dim([a.y for a in atoms]),
            dim([a.z for a in atoms]),
        )

    def _request_next_step(self) -> None:
        index = STEP_ORDER.index(self.step_name)
        if index + 1 < len(STEP_ORDER):
            self.advance_requested.emit(STEP_ORDER[index + 1])

    def _prompt_accept_system(self) -> bool:
        """Shows the post-check dialog and returns whether the user chose to
        advance to Box. Split out from _run_grompp_check() so tests can
        monkeypatch this one method to skip the blocking modal dialog.
        """
        dialog = QMessageBox(self)
        dialog.setWindowTitle("System accepted")
        dialog.setText("System accepted. Would you like to go to step 2?")
        dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        accept_button = dialog.addButton("Accept", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(accept_button)
        dialog.exec()
        return dialog.clickedButton() is accept_button

    def _prompt_inconsistent_system(self) -> None:
        """Split out from _run_grompp_check() so tests can monkeypatch this
        one method to skip the blocking modal dialog.
        """
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Inconsistent system")
        dialog.setText("The provided files does not define a consistent system")
        dialog.addButton("Accept", QMessageBox.ButtonRole.AcceptRole)
        dialog.exec()
