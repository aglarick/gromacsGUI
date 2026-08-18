from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
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
from gromacs_gui.gmx.structure_files import (
    AtomPosition,
    extract_first_instance,
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
    "Herramienta de limpieza: carga cualquier archivo de estructura o caja "
    "(.pdb o .gro), revisa qué tipos de moléculas contiene, y marca las que "
    "quieres CONSERVAR — el resto se descarta. Por defecto, todo queda "
    "marcado salvo las moléculas HETATM (agua cristalográfica, iones, "
    "ligandos u otros residuos que no forman parte de la estructura "
    "principal), si las hay. Usa el botón 'Extract all molecules' / "
    "'Extract one molecule' para elegir si quieres todas las copias de los "
    "tipos marcados o solo una — útil para aislar una única molécula de una "
    "caja combinada (p. ej. para usarla después en el paso 'Structure'). No "
    "genera topología ni avanza el flujo, y no es obligatorio usarla; puedes "
    "correrla varias veces con distintos archivos para ir armando piezas "
    "individuales."
)

_HETATM_HINT = (
    "Se detectaron moléculas HETATM (no forman parte de la estructura "
    "principal — p. ej. agua cristalográfica, iones o ligandos): {names}. "
    "Por defecto quedaron excluidas de la selección; márcalas de nuevo si "
    "las necesitas."
)


class CleanupToolWidget(QWidget):
    """Standalone structure-cleaning tool, not a pipeline step: it doesn't
    touch Project's manifest and isn't gated by (or gates) anything else.
    Cleaned files are saved wherever the user chooses via a save dialog, so
    the tool can be run repeatedly against different sources to build up
    individual molecule files.
    """

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self._input_path: Path | None = None
        self._residue_checkboxes: dict[str, QCheckBox] = {}
        self._hetatm_names: set[str] = set()
        self._atom_positions: list[AtomPosition] = []

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

        select_all_button = QPushButton("Seleccionar todo")
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        select_none_button = QPushButton("Deseleccionar todo")
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

        self._save_button = QPushButton("Guardar selección…")
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
            self._viewer.show_message("Selecciona un archivo para previsualizar.")
            return
        residues_to_keep = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }
        atoms = select_preview_atoms(
            self._atom_positions, residues_to_keep, self._extract_mode_button.isChecked()
        )
        self._viewer.set_atoms(atoms)

    def _on_save_clicked(self) -> None:
        output_path = self._prompt_save_path()
        if output_path is None:
            return
        self._save_to(output_path)

    def _prompt_save_path(self) -> Path | None:
        assert self._input_path is not None
        cleanup_dir = self.project.root / "cleanup"
        cleanup_dir.mkdir(exist_ok=True)
        suggested_name = f"{self._input_path.stem}_cleaned{self._input_path.suffix}"
        suggested_path = cleanup_dir / suggested_name
        is_pdb = self._input_path.suffix.lower() == ".pdb"
        file_filter = "PDB files (*.pdb)" if is_pdb else "GRO files (*.gro)"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Guardar archivo limpio", str(suggested_path), file_filter
        )
        return Path(path_str) if path_str else None

    def _save_to(self, output_path: Path) -> None:
        assert self._input_path is not None
        residues_to_keep = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }

        if not residues_to_keep:
            self._status_label.setText("Selecciona al menos un tipo de molécula antes de guardar.")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._extract_mode_button.isChecked():
            extract_first_instance(self._input_path, output_path, residues_to_keep)
        else:
            residues_to_remove = set(self._residue_checkboxes) - residues_to_keep
            if residues_to_remove:
                remove_residues(self._input_path, output_path, residues_to_remove)
            else:
                shutil.copyfile(self._input_path, output_path)

        self._status_label.setText(f"Guardado en: {output_path}")
