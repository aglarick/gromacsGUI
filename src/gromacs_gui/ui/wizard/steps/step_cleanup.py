from __future__ import annotations

import shutil
import warnings
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import list_heteroatom_residues
from gromacs_gui.gmx.molecule_fragments import (
    compute_fragments,
    first_fragment_with_residue,
    fragment_to_atom_positions,
)
from gromacs_gui.gmx.structure_files import (
    AtomPosition,
    list_residues,
    read_atom_positions,
    remove_residues,
    select_preview_atoms,
)
from gromacs_gui.ui.widgets.molecule_viewer import MoleculeViewer3D


def _create_viewer(parent: QWidget) -> QWidget:
    """Prefer the Mol*-based web viewer (handles far larger systems without
    choking); fall back to the matplotlib panel if QtWebEngine isn't usable
    on this machine (see utils/webengine_env.py) or fails for any other
    environment-specific reason - a broken 3D preview shouldn't take down
    the rest of the cleanup tool.
    """
    try:
        from gromacs_gui.ui.widgets.molecule_viewer_web import MoleculeViewerWeb

        return MoleculeViewerWeb(parent)
    except Exception:
        return MoleculeViewer3D(parent)


_DESCRIPTION = (
    "Cleanup tool: load any structure or box file (.pdb or .gro), review "
    "what molecule types it contains, and check the ones you want to "
    "KEEP — everything else is discarded. By default, everything is kept "
    "except HETATM molecules (crystallographic water, ions, ligands, or "
    "other residues that aren't part of the main structure), if any. Use "
    "the 'Extract all molecules' / 'Extract one molecule' button to choose "
    "whether you want every copy of the checked types or just one — useful "
    "for isolating a single molecule out of a combined box (e.g. to use "
    "later in the 'Structure' step). 'Extract one molecule' identifies the "
    "whole molecule by its chemical connectivity, not by residue — a "
    "polymer split across several monomers sharing the same residue name "
    "(e.g. 1P3HT, 2P3HT, 3P3HT…) gets extracted whole, not just the first "
    "monomer. This doesn't generate a topology or advance the pipeline, "
    "and using it isn't required; you can run it several times against "
    "different files to build up individual pieces."
)

_HETATM_HINT = (
    "HETATM molecules were detected (not part of the main structure — e.g. "
    "crystallographic water, ions, or ligands): {names}. They were excluded "
    "from the selection by default; check them again if you need them."
)


class CleanupToolWidget(QWidget):
    """Standalone structure-cleaning tool, not a pipeline step: it doesn't
    touch Project's manifest and isn't gated by (or gates) anything else.
    Cleaned files are saved wherever the user chooses via a save dialog, so
    the tool can be run repeatedly against different sources to build up
    individual molecule files.
    """

    def __init__(
        self, project: Project | None, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self._input_path: Path | None = None
        self._residue_checkboxes: dict[str, QCheckBox] = {}
        self._hetatm_names: set[str] = set()
        self._atom_positions: list[AtomPosition] = []
        self._fragments: list | None = None  # lazily computed, see _first_matching_fragment

        description = QLabel(_DESCRIPTION, self)
        description.setWordWrap(True)

        self._hetatm_hint_label = QLabel("", self)
        self._hetatm_hint_label.setWordWrap(True)
        self._hetatm_hint_label.setVisible(False)

        self._input_label = QLabel("No file selected")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse_clicked)
        picker_row = QHBoxLayout()
        picker_row.addWidget(self._input_label, 1)
        picker_row.addWidget(browse_button)

        select_all_button = QPushButton("Select all")
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        select_none_button = QPushButton("Deselect all")
        select_none_button.clicked.connect(lambda: self._set_all_checked(False))
        self._extract_mode_button = QPushButton("Extract all molecules")
        self._extract_mode_button.setCheckable(True)
        self._extract_mode_button.toggled.connect(self._on_extract_mode_toggled)
        select_row = QHBoxLayout()
        select_row.addWidget(select_all_button)
        select_row.addWidget(select_none_button)
        select_row.addStretch(1)
        select_row.addWidget(self._extract_mode_button)

        self._residue_list_layout = QVBoxLayout()

        self._save_button = QPushButton("Save selection…")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._on_save_clicked)

        self._status_label = QLabel("", self)
        self._status_label.setWordWrap(True)

        self._viewer = _create_viewer(self)

        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addWidget(self._hetatm_hint_label)
        layout.addLayout(picker_row)
        layout.addLayout(select_row)
        layout.addLayout(self._residue_list_layout)
        layout.addWidget(self._save_button)
        layout.addWidget(self._status_label)
        layout.addWidget(self._viewer, 1)

    def _on_browse_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a structure or box file",
            str(Path.home()),
            "Structure files (*.pdb *.gro)",
        )
        if not path:
            return
        self._set_input_path(Path(path))

    def _set_input_path(self, path: Path) -> None:
        self._input_path = path
        self._input_label.setText(path.name)
        self._status_label.setText("")
        self._rebuild_residue_checklist()

    def _rebuild_residue_checklist(self) -> None:
        while self._residue_list_layout.count():
            item = self._residue_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._residue_checkboxes.clear()
        self._fragments = None

        if self._input_path is None:
            self._save_button.setEnabled(False)
            self._hetatm_hint_label.setVisible(False)
            self._atom_positions = []
            self._refresh_preview()
            return

        residues = list_residues(self._input_path)
        self._hetatm_names = self._detect_hetatm_names(self._input_path)
        self._atom_positions = read_atom_positions(self._input_path)
        default_kept = set(residues) - self._hetatm_names

        if self._hetatm_names:
            self._hetatm_hint_label.setText(
                _HETATM_HINT.format(names=", ".join(sorted(self._hetatm_names)))
            )
            self._hetatm_hint_label.setVisible(True)
        else:
            self._hetatm_hint_label.setVisible(False)

        for name, count in sorted(residues.items()):
            tag = " [HETATM]" if name in self._hetatm_names else ""
            checkbox = QCheckBox(f"{name}{tag} ×{count}")
            checkbox.setChecked(name in default_kept)
            checkbox.stateChanged.connect(self._refresh_preview)
            self._residue_list_layout.addWidget(checkbox)
            self._residue_checkboxes[name] = checkbox

        self._save_button.setEnabled(bool(residues))
        self._refresh_preview()

    @staticmethod
    def _detect_hetatm_names(path: Path) -> set[str]:
        """Which residue names are HETATM records - only meaningful for
        .pdb, since .gro has no ATOM/HETATM distinction to scan at all.
        """
        if path.suffix.lower() == ".pdb":
            return set(list_heteroatom_residues(path))
        return set()

    def _set_all_checked(self, checked: bool) -> None:
        for checkbox in self._residue_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        self._refresh_preview()

    def _on_extract_mode_toggled(self, checked: bool) -> None:
        self._extract_mode_button.setText(
            "Extract one molecule" if checked else "Extract all molecules"
        )
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self._atom_positions:
            self._viewer.show_message("Select a file to preview.")
            return
        residues_to_keep = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }
        if self._extract_mode_button.isChecked():
            fragment = self._first_matching_fragment(residues_to_keep)
            if fragment is None:
                self._viewer.show_message("No connected fragment matches the checked types.")
                return
            self._viewer.set_atoms(fragment_to_atom_positions(fragment))
            return
        atoms = select_preview_atoms(self._atom_positions, residues_to_keep)
        self._viewer.set_atoms(atoms)

    def _first_matching_fragment(self, residue_names: set[str]):
        """Molecules are grouped by actual bond connectivity (guessed from
        geometry), not by residue name/number - a polymer chain split
        across many identically-named residues (e.g. every P3HT monomer is
        its own "P3HT" residue) is one fragment, and residue numbers that
        collide across independently-built chains never get confused for
        the same molecule.
        """
        if not residue_names:
            return None
        if self._fragments is None:
            assert self._input_path is not None
            self._status_label.setText("Computing molecular connectivity…")
            QApplication.processEvents()
            self._fragments = compute_fragments(self._input_path)
            self._status_label.setText("")
        return first_fragment_with_residue(self._fragments, residue_names)

    def _on_save_clicked(self) -> None:
        output_path = self._prompt_save_path()
        if output_path is None:
            return
        self._save_to(output_path)

    def _prompt_save_path(self) -> Path | None:
        assert self._input_path is not None
        if self.project is not None:
            cleanup_dir = self.project.root / "cleanup"
            cleanup_dir.mkdir(exist_ok=True)
        else:
            cleanup_dir = self._input_path.parent
        suggested_name = f"{self._input_path.stem}_cleaned{self._input_path.suffix}"
        suggested_path = cleanup_dir / suggested_name
        is_pdb = self._input_path.suffix.lower() == ".pdb"
        file_filter = "PDB files (*.pdb)" if is_pdb else "GRO files (*.gro)"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save cleaned file", str(suggested_path), file_filter
        )
        return Path(path_str) if path_str else None

    def _save_to(self, output_path: Path) -> None:
        assert self._input_path is not None
        residues_to_keep = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }

        if not residues_to_keep:
            self._status_label.setText("Select at least one molecule type before saving.")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._extract_mode_button.isChecked():
            fragment = self._first_matching_fragment(residues_to_keep)
            if fragment is None:
                self._status_label.setText("No connected fragment matches the checked types.")
                return
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fragment.atoms.write(str(output_path))
        else:
            residues_to_remove = set(self._residue_checkboxes) - residues_to_keep
            if residues_to_remove:
                remove_residues(self._input_path, output_path, residues_to_remove)
            else:
                shutil.copyfile(self._input_path, output_path)

        self._status_label.setText(f"Saved to: {output_path}")
